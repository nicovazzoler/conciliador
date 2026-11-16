"""API HTTP. Solo traduce: cada endpoint llama a las mismas funciones que la terminal."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from conciliador import base, capturas, clasificar, cotizaciones, esquemas, importar, inversiones, manual, plan, precios, reporte, revisar

MAXIMO_ARCHIVO = 20 * 1024 * 1024  # 20 MB: un resumen pesa menos de 1.
MINIMO_REGLA = 3  # Una regla "Pa" alcanzaría a Pago, Pasaje, Panadería...

HOST = "127.0.0.1"  # Sin login: solo esta máquina puede entrar.
PUERTO = 8000
PAGINA = Path(__file__).parent.parent / "web" / "dist"


def crear_app(
    ruta_db: Path,
    entrada: Path = Path("entrada"),
    clave_nacion: str = "",
    traer_cotizaciones=cotizaciones.traer,
    traer_precio=precios._json,
    clave_anthropic: str = "",
    leer_capturas=None,
) -> FastAPI:
    """Una app por base: los tests usan una temporal y el comando `web`, la real.

    La clave del PDF de Nación y la de Anthropic las recibe el servidor al arrancar y nunca viajan a la página.
    """
    if leer_capturas is None:
        def leer_capturas(imagenes):
            return capturas.leer(imagenes, clave_anthropic)

    motor = base.conectar(ruta_db)  # Si la base está desactualizada, falla al arrancar.
    app = FastAPI(title="Conciliador")

    @app.get("/api/reporte/{mes}", response_model=esquemas.Reporte)
    def ver_reporte(mes: str):
        try:
            return asdict(reporte.armar(motor, mes))
        except ValueError as error:  # Un mes mal escrito es un error de quien llama.
            raise HTTPException(status_code=422, detail=str(error))

    @app.get("/api/historial/{mes}", response_model=list[esquemas.MesHistorial])
    def ver_historial(mes: str, meses: int = 6):
        try:
            return reporte.historial(motor, mes, meses)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

    @app.post(
        "/api/gastos",
        status_code=201,
        response_model=esquemas.Guardado,
        responses={409: {"model": esquemas.Avisos, "description": "Hay avisos: falta confirmar"}},
    )
    def cargar_gasto(gasto: esquemas.GastoNuevo):
        try:
            fecha = manual.leer_fecha((gasto.fecha or date.today()).isoformat())
            fila = manual.preparar_gasto(gasto.monto, gasto.descripcion, fecha, gasto.moneda, gasto.medio)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        avisos = manual.evaluar_gasto(motor, fila)
        if avisos and not gasto.confirmado:
            return JSONResponse(
                status_code=409,
                content={"avisos": [{"codigo": a.codigo, "mensaje": a.mensaje} for a in avisos]},
            )
        movimiento_id, categoria, plan_concepto = manual.guardar_gasto(
            motor, fila, gasto.medio, gasto.categoria
        )
        return {"id": movimiento_id, "categoria": categoria, "plan_concepto": plan_concepto}

    @app.post("/api/pagos", status_code=201, response_model=esquemas.Guardado)
    def cargar_pago(pago: esquemas.PagoNuevo):
        try:
            fecha = manual.leer_fecha((pago.fecha or date.today()).isoformat())
            return {"id": manual.guardar_pago(motor, pago.tarjeta, pago.monto, fecha, pago.moneda)}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

    @app.get("/api/manuales", response_model=list[esquemas.Manual])
    def ver_manuales(cantidad: int = 10):
        return base.manuales(motor, cantidad)

    @app.delete("/api/manuales/{movimiento_id}", status_code=204)
    def borrar_manual(movimiento_id: int):
        if not base.borrar_manual(motor, movimiento_id):
            raise HTTPException(status_code=404, detail="no hay un gasto o pago cargado a mano con ese número")
        return Response(status_code=204)

    @app.get("/api/pendientes", response_model=list[esquemas.Pendiente])
    def ver_pendientes():
        return [
            {**vars(p), "sugerido": revisar.texto_sugerido(p.descripcion)} for p in base.pendientes(motor)
        ]

    @app.post("/api/pendientes/{movimiento_id}", status_code=204)
    def resolver(movimiento_id: int, resolucion: esquemas.Resolucion):
        if not base.es_pendiente(motor, movimiento_id):
            raise HTTPException(status_code=404, detail="ese movimiento no está para revisar")
        if resolucion.cambio:
            base.marcar_cambio(motor, movimiento_id)
            return Response(status_code=204)
        categoria = (resolucion.categoria or "").strip()
        if not categoria:
            raise HTTPException(status_code=422, detail="falta la categoría, o marcarlo como cambio")
        regla = (resolucion.regla or "").strip() or None
        if regla is not None and len(regla) < MINIMO_REGLA:
            raise HTTPException(status_code=422, detail=f"la regla necesita al menos {MINIMO_REGLA} letras")
        base.resolver_pendiente(motor, movimiento_id, categoria, regla)
        return Response(status_code=204)

    @app.get("/api/plan", response_model=esquemas.Plan)
    def ver_plan():
        return base.plan_con_ids(motor)

    @app.get("/api/plan.csv", response_class=PlainTextResponse)
    def exportar_plan():
        leido = base.leer_plan(motor)
        return PlainTextResponse(
            plan.a_csv(leido.fijos, leido.cuotas),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="plan.csv"'},
        )

    def _guardar(tabla: str, item_id: int | None, construir):
        try:
            item = construir()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        try:
            guardado = base.guardar_del_plan(motor, tabla, item, item_id)
        except base.ConceptoRepetido as error:
            raise HTTPException(status_code=409, detail=str(error))
        if guardado is None:
            raise HTTPException(status_code=404, detail="no existe en el plan")
        return {"id": guardado}

    def _fijo(e: esquemas.FijoEntrada):
        return lambda: plan.fijo_desde(e.concepto, e.texto, e.monto, e.moneda, e.dia, e.categoria)

    def _cuota(e: esquemas.CuotaEntrada):
        return lambda: plan.cuota_desde(e.concepto, e.texto, e.monto, e.moneda, e.cantidad, e.primer_mes, e.categoria)

    @app.post("/api/plan/fijos", status_code=201, response_model=esquemas.Guardado)
    def crear_fijo(entrada: esquemas.FijoEntrada):
        return _guardar("fijos", None, _fijo(entrada))

    @app.put("/api/plan/fijos/{item_id}", response_model=esquemas.Guardado)
    def editar_fijo(item_id: int, entrada: esquemas.FijoEntrada):
        return _guardar("fijos", item_id, _fijo(entrada))

    @app.post("/api/plan/cuotas", status_code=201, response_model=esquemas.Guardado)
    def crear_cuota(entrada: esquemas.CuotaEntrada):
        return _guardar("cuotas", None, _cuota(entrada))

    @app.put("/api/plan/cuotas/{item_id}", response_model=esquemas.Guardado)
    def editar_cuota(item_id: int, entrada: esquemas.CuotaEntrada):
        return _guardar("cuotas", item_id, _cuota(entrada))

    @app.delete("/api/plan/{tabla}/{item_id}", status_code=204)
    def borrar_del_plan(tabla: Literal["fijos", "cuotas"], item_id: int):
        if not base.borrar_del_plan(motor, tabla, item_id):
            raise HTTPException(status_code=404, detail="no existe en el plan")
        return Response(status_code=204)

    @app.get("/api/inversiones/{mes}", response_model=esquemas.Inversiones)
    def ver_inversiones(mes: str):
        if not reporte.MES.match(mes):
            raise HTTPException(status_code=422, detail=f"mes inválido: {mes!r}")
        return armar_inversiones(motor, mes)

    @app.post("/api/operaciones", status_code=201, response_model=esquemas.Guardado)
    def cargar_operacion(nueva: esquemas.OperacionNueva):
        try:
            if nueva.fecha > date.today():
                raise ValueError("la fecha es futura")
            activo = nueva.activo.strip().upper()
            if not activo or len(activo) > 20:
                raise ValueError("falta el activo, por ejemplo BTC o NVDA")
            cantidad = inversiones.decimal_desde(nueva.cantidad, "cantidad")
            precio = inversiones.decimal_desde(nueva.precio, "precio")
            if cantidad == 0 or precio == 0:
                raise ValueError("la cantidad y el precio tienen que ser mayores que 0")
            moneda = nueva.moneda.strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", moneda):
                raise ValueError("la moneda va con su código de tres letras: USD, BRL, EUR")
            op = inversiones.Operacion(
                0, datetime.combine(nueva.fecha, datetime.min.time()), activo, nueva.tipo_activo, nueva.lado,
                cantidad, precio, inversiones.decimal_desde(nueva.comision or "0", "comisión"), moneda=moneda,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        try:
            tipo_cambio = precios.cambio(moneda, nueva.fecha, traer_precio)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            raise HTTPException(status_code=502, detail=f"no se pudo saber cuánto valía el {moneda} ese día: probá de nuevo")
        numero = nueva.numero_operacion or (huella(op) if nueva.fuente != "manual" else uuid4().hex)
        if not base.guardar_operacion(motor, nueva.fuente, numero, op, tipo_cambio):
            raise HTTPException(status_code=409, detail=f"esa operación de {op.activo} ya estaba cargada")
        return {"id": max(o.id for o in base.operaciones(motor))}

    @app.post("/api/operaciones/leer", response_model=esquemas.LecturaCapturas)
    def leer_operaciones(archivos: list[UploadFile]):
        """Lee las capturas con Claude. No guarda nada: devuelve lo leído para revisarlo."""
        if not archivos or len(archivos) > capturas.MAXIMO_CAPTURAS:
            raise HTTPException(status_code=422, detail=f"mandá entre 1 y {capturas.MAXIMO_CAPTURAS} capturas")
        imagenes = []
        try:
            for archivo in archivos:
                contenido = archivo.file.read()
                capturas.revisar_captura(contenido, archivo.content_type)
                imagenes.append((contenido, archivo.content_type))
        except capturas.CapturaError as error:
            raise HTTPException(status_code=422, detail=str(error))
        try:
            return leer_capturas(imagenes)
        except capturas.CapturaError as error:
            raise HTTPException(status_code=502, detail=str(error))

    @app.delete("/api/operaciones/{operacion_id}", status_code=204)
    def borrar_operacion(operacion_id: int):
        if not base.borrar_operacion(motor, operacion_id):
            raise HTTPException(status_code=404, detail="no existe esa operación")
        return Response(status_code=204)

    @app.post("/api/precios", response_model=esquemas.PreciosActualizados)
    def actualizar_precios():
        abiertas = inversiones.calcular(base.operaciones(motor), {}).posiciones
        tipos = {p.activo: p.tipo_activo for p in abiertas}
        nuevos, errores = precios.actualizar(tipos, traer_precio)
        origen = {a: ("binance" if tipos[a] == "cripto" else "yahoo") for a in nuevos}
        base.guardar_precios(motor, nuevos, origen, datetime.now())
        errores += revisar_niveles(tipos)
        return {"actualizados": len(nuevos), "errores": errores}

    def revisar_niveles(tipos: dict[str, str]) -> list[str]:
        """Si hoy el precio llegó al stop loss o al take profit de una posición abierta, queda avisado."""
        errores = []
        for activo, nivel in base.niveles(motor).items():
            if activo not in tipos or nivel["tocado"]:
                continue
            try:
                bajo, alto, moneda = precios.extremos(activo, tipos[activo], traer_precio)
            except precios.FALLAS as error:
                errores.append(f"{activo}: no se pudo revisar el stop loss ({type(error).__name__})")
                continue
            if moneda != nivel["moneda"]:
                errores.append(f"{activo}: cotiza en {moneda} y el stop loss está en {nivel['moneda']}")
            elif nivel["stop_loss"] is not None and bajo <= nivel["stop_loss"]:
                base.marcar_tocado(motor, activo, "stop_loss", date.today())
            elif nivel["take_profit"] is not None and alto >= nivel["take_profit"]:
                base.marcar_tocado(motor, activo, "take_profit", date.today())
        return errores

    @app.put("/api/niveles/{activo}", status_code=204)
    def guardar_niveles(activo: str, entrada: esquemas.NivelesEntrada):
        activo = activo.strip().upper()
        try:
            leidos = [
                None if not (texto or "").strip() else inversiones.decimal_desde(texto, nombre)
                for texto, nombre in ((entrada.stop_loss, "stop loss"), (entrada.take_profit, "take profit"))
            ]
            moneda = entrada.moneda.strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", moneda):
                raise ValueError("la moneda va con su código de tres letras")
            if all(leidos) and leidos[0] >= leidos[1]:
                raise ValueError("el stop loss tiene que estar debajo del take profit")
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        base.guardar_niveles(motor, activo, moneda, *leidos)
        return Response(status_code=204)

    @app.post("/api/niveles/{activo}/cerrar", status_code=201, response_model=esquemas.Guardado)
    def cerrar_por_nivel(activo: str):
        """Confirma que la posición se cerró en el nivel: carga la venta de todo lo que había, a ese precio."""
        nivel = base.niveles(motor).get(activo)
        abierta = next((p for p in inversiones.calcular(base.operaciones(motor), {}).posiciones if p.activo == activo), None)
        if nivel is None or not nivel["tocado"] or abierta is None:
            raise HTTPException(status_code=404, detail=f"no hay un stop loss o take profit tocado en {activo}")
        precio, dia = nivel[nivel["tocado"]], nivel["tocado_el"]
        try:
            tipo_cambio = precios.cambio(nivel["moneda"], dia, traer_precio)
        except precios.FALLAS:
            raise HTTPException(status_code=502, detail=f"no se pudo saber cuánto valía el {nivel['moneda']} ese día")
        venta = inversiones.Operacion(0, datetime.combine(dia, datetime.min.time()), activo, abierta.tipo_activo, "venta",
                                      abierta.cantidad, precio, Decimal(0), moneda=nivel["moneda"])
        base.guardar_operacion(motor, "manual", uuid4().hex, venta, tipo_cambio)
        base.borrar_niveles(motor, activo)
        return {"id": max(o.id for o in base.operaciones(motor))}

    @app.post("/api/niveles/{activo}/descartar", status_code=204)
    def descartar_nivel(activo: str):
        """No se cerró: se borra el aviso y los niveles quedan como estaban."""
        base.marcar_tocado(motor, activo, None, None)
        return Response(status_code=204)

    historia_guardada: dict = {}

    @app.get("/api/historia-inversiones", response_model=esquemas.HistoriaInversiones)
    def ver_historia():
        """La cartera día por día, del último año como mucho. Los precios viejos se piden una vez por día."""
        ops = base.operaciones(motor)
        if not ops:
            return {"puntos": [], "sin_precio": []}
        hoy = date.today()
        desde = max(min(o.fecha_hora.date() for o in ops), hoy - timedelta(days=365))
        tipos = {o.activo: o.tipo_activo for o in ops}
        def bajar(activo: str):
            try:
                return precios.cierres(activo, tipos[activo], desde, traer_precio)
            except precios.FALLAS:
                return None

        faltan = [a for a in sorted(tipos) if (a, desde, hoy) not in historia_guardada]
        with ThreadPoolExecutor(max_workers=6) as hilos:  # Un pedido por activo, todos a la vez.
            for activo, serie in zip(faltan, hilos.map(bajar, faltan)):
                historia_guardada[(activo, desde, hoy)] = serie
        series, sin_precio = {}, []
        for activo in sorted(tipos):
            clave = (activo, desde, hoy)
            if historia_guardada[clave]:
                series[activo] = historia_guardada[clave]
            else:
                sin_precio.append(activo)
        c = inversiones.a_centavos
        return {
            "puntos": [
                {"fecha": p["fecha"], "valor_centavos": c(p["valor"]), "invertido_centavos": c(p["invertido"])}
                for p in inversiones.historia(ops, series, desde, hoy)
            ],
            "sin_precio": sin_precio,
        }

    @app.get("/api/movimientos/{mes}", response_model=esquemas.MovimientosDelMes)
    def ver_movimientos(mes: str):
        if not reporte.MES.match(mes):
            raise HTTPException(status_code=422, detail=f"mes inválido: {mes!r}")
        filas = base.movimientos_del_mes(motor, mes)
        pesos = [f for f in filas if f["moneda"] == "ARS"]
        return {
            "mes": mes,
            "entro_centavos": sum(f["monto_centavos"] for f in pesos if f["tipo"] == "ingreso"),
            "salio_centavos": -sum(f["monto_centavos"] for f in pesos if f["tipo"] in ("consumo", "cuota", "impuesto")),
            "movimientos": filas,
        }

    @app.put("/api/movimientos/{movimiento_id}/categoria", status_code=204)
    def elegir_categoria(movimiento_id: int, elegida: esquemas.CategoriaElegida):
        categoria = (elegida.categoria or "").strip() or None
        if not base.poner_categoria(motor, movimiento_id, categoria):
            raise HTTPException(status_code=404, detail="no existe ese movimiento")
        return Response(status_code=204)

    @app.get("/api/categorias/detalle", response_model=list[esquemas.CategoriaDetalle])
    def ver_categorias_detalle():
        return base.categorias_detalle(motor)

    @app.post("/api/categorias/renombrar", response_model=esquemas.Renombrada)
    def renombrar_categoria(renombre: esquemas.Renombre):
        de, a = renombre.de.strip(), renombre.a.strip()
        if not de or not a or de == a:
            raise HTTPException(status_code=422, detail="hace falta el nombre actual y uno nuevo, distinto")
        if a == clasificar.SIN_REGLA:
            raise HTTPException(status_code=422, detail=f"{a!r} no es una categoría: es lo que no tiene ninguna")
        return {"movimientos": base.renombrar_categoria(motor, de, a)}

    @app.delete("/api/categorias/{nombre:path}", status_code=204)
    def borrar_categoria(nombre: str):
        base.borrar_categoria(motor, nombre)
        return Response(status_code=204)

    @app.get("/api/reglas", response_model=list[esquemas.ReglaDetalle])
    def ver_reglas():
        return base.reglas(motor)

    @app.put("/api/reglas/{regla_id}", status_code=204)
    def editar_regla(regla_id: int, regla: esquemas.ReglaEditada):
        texto, categoria = regla.texto.strip(), regla.categoria.strip()
        if len(texto) < MINIMO_REGLA or not categoria:
            raise HTTPException(status_code=422, detail=f"la regla necesita al menos {MINIMO_REGLA} letras y una categoría")
        try:
            existe = base.editar_regla(motor, regla_id, texto, categoria)
        except base.ReglaRepetida as error:
            raise HTTPException(status_code=409, detail=str(error))
        if not existe:
            raise HTTPException(status_code=404, detail="no existe esa regla")
        return Response(status_code=204)

    @app.delete("/api/reglas/{regla_id}", status_code=204)
    def borrar_regla(regla_id: int):
        if not base.editar_regla(motor, regla_id, None, None):
            raise HTTPException(status_code=404, detail="no existe esa regla")
        return Response(status_code=204)

    @app.get("/api/categorias", response_model=list[str])
    def ver_categorias():
        return base.categorias(motor)

    @app.get("/api/varios", response_model=list[esquemas.GrupoVarios])
    def ver_varios():
        return revisar.agrupar_varios(motor)

    @app.post("/api/reglas", status_code=201, response_model=esquemas.ReglaGuardada)
    def crear_regla(regla: esquemas.ReglaNueva):
        texto, categoria = regla.texto.strip(), regla.categoria.strip()
        if len(texto) < MINIMO_REGLA or not categoria:
            raise HTTPException(
                status_code=422, detail=f"la regla necesita al menos {MINIMO_REGLA} letras y una categoría"
            )
        try:
            return {"categorizados": base.agregar_regla(motor, texto, categoria)}
        except base.ReglaRepetida as error:
            raise HTTPException(status_code=409, detail=str(error))

    @app.post("/api/importar", response_model=esquemas.Importacion)
    def importar_archivos(archivos: list[UploadFile]):
        informes = [_importar_uno(archivo, motor, entrada, clave_nacion) for archivo in archivos]
        base.aplicar_reglas(motor)
        aviso = importar.actualizar_cotizaciones(motor, traer_cotizaciones)
        return {
            "informes": informes,
            "aviso_cotizaciones": aviso,
            "pendientes": len(base.pendientes(motor)),
            "sin_usd": base.contar_sin_usd(motor),
        }

    # La página ya armada (`npm run build`). Va al final para que /api/... no caiga acá.
    if PAGINA.is_dir():
        app.mount("/", StaticFiles(directory=PAGINA, html=True), name="pagina")

    return app


def esquema_openapi() -> dict:
    """El esquema de la API, para generar los tipos de TypeScript. Usa una base descartable."""
    with tempfile.TemporaryDirectory() as carpeta:
        return crear_app(Path(carpeta) / "esquema.db").openapi()


def armar_inversiones(motor: base.Engine, mes: str) -> dict:
    """Cartera de hoy, y lo realizado, las comisiones y las operaciones del mes pedido."""
    ops = base.operaciones(motor)
    guardados, precios_al = base.precios(motor)
    resultado = inversiones.calcular(ops, guardados)
    c = inversiones.a_centavos
    abiertas = {p.activo for p in resultado.posiciones}
    niveles = base.niveles(motor)
    moneda_de = {o.activo: o.moneda for o in sorted(ops, key=lambda o: (o.fecha_hora, o.id))}
    cantidad_de = {p.activo: p.cantidad for p in resultado.posiciones}
    del_mes = sorted(inversiones.por_mes(ops).get(mes, []), key=lambda o: (o.fecha_hora, o.id), reverse=True)
    con_precio = [p for p in resultado.posiciones if p.valor is not None]
    return {
        "mes": mes,
        "cartera_centavos": c(sum((p.valor for p in con_precio), Decimal(0))),
        "invertido_centavos": c(sum((p.costo for p in resultado.posiciones), Decimal(0))),
        "no_realizado_centavos": c(sum((p.no_realizado for p in con_precio), Decimal(0))),
        "realizado_mes_centavos": c(sum((resultado.realizado.get(o.id, Decimal(0)) for o in del_mes), Decimal(0))),
        "comisiones_mes_centavos": c(sum((o.comision for o in del_mes), Decimal(0))),
        "operaciones_mes": len(del_mes),
        "sin_precio": [p.activo for p in resultado.posiciones if p.precio is None],
        "precios_al": precios_al,
        "avisos": resultado.avisos,
        "niveles_tocados": [
            {
                "activo": activo, "tipo": n["tocado"], "nivel": inversiones.formato(n[n["tocado"]]), "moneda": n["moneda"],
                "fecha": n["tocado_el"], "cantidad": inversiones.formato(cantidad_de[activo]),
            }
            for activo, n in sorted(niveles.items())
            if n["tocado"] and activo in abiertas
        ],
        "posiciones": [
            {
                "activo": p.activo, "tipo_activo": p.tipo_activo, "cantidad": inversiones.formato(p.cantidad),
                "costo_promedio": inversiones.formato(p.costo_promedio.quantize(Decimal("0.0001"))),
                "invertido_centavos": c(p.costo),
                "precio": None if p.precio is None else inversiones.formato(p.precio),
                "valor_centavos": c(p.valor), "no_realizado_centavos": c(p.no_realizado),
                "moneda": niveles.get(p.activo, {}).get("moneda") or moneda_de.get(p.activo, "USD"),
                "stop_loss": texto_nivel(niveles.get(p.activo, {}).get("stop_loss")),
                "take_profit": texto_nivel(niveles.get(p.activo, {}).get("take_profit")),
            }
            for p in resultado.posiciones
        ],
        "operaciones": [
            {
                "id": o.id, "fecha": o.fecha_hora.date(), "activo": o.activo, "tipo_activo": o.tipo_activo,
                "lado": o.lado, "cantidad": inversiones.formato(o.cantidad),
                "precio": inversiones.formato(o.precio_moneda if o.precio_moneda is not None else o.precio),
                "moneda": o.moneda,
                "comision_centavos": c(o.comision), "resultado_centavos": c(resultado.realizado.get(o.id)),
                "abierta": o.lado == "compra" and o.activo in abiertas,
            }
            for o in del_mes
        ],
    }


def texto_nivel(valor: Decimal | None) -> str | None:
    return None if valor is None else inversiones.formato(valor)


def nombre_seguro(nombre: str | None) -> str | None:
    """Solo el nombre final, sin carpetas: '../../x.pdf' queda 'x.pdf'. None si no se acepta."""
    final = Path((nombre or "").replace("\\", "/")).name
    if not final or final.startswith("."):
        return None
    if final != plan.ARCHIVO and Path(final).suffix.lower() != ".pdf":
        return None
    return final


def _importar_uno(archivo: UploadFile, motor: base.Engine, entrada: Path, clave_nacion: str) -> dict:
    nombre = nombre_seguro(archivo.filename)
    if nombre is None:
        return _rechazado(archivo.filename or "(sin nombre)", "solo se aceptan PDF o plan.csv")
    contenido = archivo.file.read(MAXIMO_ARCHIVO + 1)
    if len(contenido) > MAXIMO_ARCHIVO:
        return _rechazado(nombre, "pesa más de 20 MB")

    # Se importa desde una carpeta temporal: si no se reconoce, no pisa un archivo bueno de entrada/.
    with tempfile.TemporaryDirectory() as carpeta:
        temporal = Path(carpeta) / nombre
        temporal.write_bytes(contenido)
        informe = importar.importar_archivo(temporal, motor, clave_nacion)
        if informe.reconocido:
            entrada.mkdir(exist_ok=True)
            shutil.move(temporal, entrada / nombre)
    return asdict(informe)


def _rechazado(nombre: str, motivo: str) -> dict:
    return asdict(importar.Informe(nombre, errores=[motivo]))


def huella(op: inversiones.Operacion) -> str:
    """Sin número de operación, lo leído se reconoce por sus datos: la misma captura no carga dos veces."""
    datos = f"{op.fecha_hora.date()}|{op.activo}|{op.lado}|{op.cantidad.normalize()}|{op.precio.normalize()}"
    return "captura-" + hashlib.sha256(datos.encode()).hexdigest()[:16]


def servir(ruta_db: Path, entrada: Path = Path("entrada"), clave_nacion: str = "", clave_anthropic: str = "") -> None:
    uvicorn.run(crear_app(ruta_db, entrada, clave_nacion, clave_anthropic=clave_anthropic), host=HOST, port=PUERTO)
