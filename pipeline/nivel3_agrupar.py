#!/usr/bin/env python3
"""
Nivel 3 — Agrupa las filas de Time & Sales (nivel 2) en operaciones que
parecen pertenecer al mismo actor.

Las condiciones multi-leg (MULTI_LEG) y las de una pata se agrupan aparte:
una operación nunca mezcla las dos.

Condiciones multi-leg, dos mecanismos combinados por union-find:

  A) Cruce entre contratos (patas de una misma orden multi-leg):
     filas de contratos DISTINTOS del mismo subyacente, con la misma Trade
     Condition, ejecutadas prácticamente en el mismo instante (<= TOL_MS).
     Una orden multi-leg imprime todas sus patas con el mismo timestamp.

  B) Troceado dentro del mismo contrato:
     filas del MISMO contrato, con la MISMA Trade Condition, separadas
     por VENTANA_S segundos o menos.

Condiciones de una pata (AUTO, SLAN, ISOI...): nunca se unen contratos
distintos. Dentro de cada contrato y condición:

  1) Ráfaga: trades del mismo lado (compra, venta o indeterminado; ver
     lado()) separados por VENTANA_RAFAGA_S segundos o menos forman un trozo.
  2) Un trozo es relevante si su premium alcanza el menor entre el umbral
     del subyacente y FRACCION_ESTIMADO del premium_estimado del contrato
     en el nivel 1 (sin estimado, FRACCION_ESTIMADO del umbral).
  3) Los trozos relevantes, por orden de inicio, se unen a la operación en
     curso si empiezan VENTANA_S segundos o menos después de su último
     trade y su lado es compatible (igual, o alguno indeterminado). El lado
     de la operación es el del primer trozo con lado; un trozo del lado
     contrario abre otra operación.
  4) Un trozo no relevante es una operación propia y no se encadena.

Así no se encadenan trades pequeños de actores distintos durante minutos
ni se mezclan compras y ventas. Ningún trade desaparece.

Uso por línea de comandos, como lo ejecuta el pipeline (sin cambios respecto a
versiones anteriores):

  python3 nivel3_agrupar.py nivel2_trades_YYYYMMDD.csv \
      nivel1_candidatos_YYYYMMDD.csv nivel3_operaciones_YYYYMMDD.csv

Uso como módulo (dashboard). Las piezas que componen main() se pueden
llamar por separado, para agrupar y aplicar ediciones manuales antes de
filtrar por umbral:

  preparar_filas(filas, fieldnames) -> filas de trade listas para agrupar
  quitar_cancelaciones(rows)        -> (filas sin cancelaciones ni trades anulados, pares)
  cargar_nivel1(path)               -> (precio por símbolo, premium_estimado por contrato)
  agrupar(rows, precios, estimados) -> {raíz: [filas]} (un grupo = una operación)
  patas_de(grupo)                   -> detalle por pata (resumen_pata de cada contrato)
  resumen(grupo)                    -> fila de nivel3_operaciones (premium en $)
  id_operacion(grupo)               -> 'YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC'
  ids_operaciones(grupos)           -> {raíz: ID único en la captura}
  resumir_todas(grupos)             -> resúmenes ordenados por premium descendente
  pasa_umbral(premium, precio)      -> bool, umbral por tramo de precio
  filtrar_por_umbral(todas, precios) -> (operaciones que pasan, nº descartadas)

Historial de la salida:
  01/10/2026  versión de referencia.
  19/10/2026  las cancelaciones (CANC, CNCL, CNCO, CNOL) se quitan antes de
              agrupar, junto con el trade que anulan. Con un nivel 2 sin
              cancelaciones la salida es idéntica byte a byte a la de la
              versión de referencia (lo comprueba el test de no regresión del
              repositorio del dashboard); si hay cancelaciones, es idéntica a
              la de la versión de referencia sobre el mismo nivel 2 sin esas
              filas, y la consola añade una línea con el recuento.
  16/11/2026  nueva regla de agrupación para las condiciones de una pata
              (ráfagas, trozos relevantes y encadenado por lado); el cruce
              de 50 ms solo une condiciones multi-leg; el 0,25 exacto de
              agresividad es indeterminado también en 'direccion' y en el
              precio neto. Columnas nuevas al final: lado, n_trozos,
              premium_trozo_mayor_M y lado_de_trozo_menor. Las operaciones
              de condiciones multi-leg no cambian.
"""

import csv, sys, collections
from datetime import datetime

VENTANA_S = 120.0          # multi-leg: separación máxima entre trades del mismo contrato;
                           # una pata: entre un trozo y el último trade de la operación
TOL_MS    = 50             # tolerancia para considerar dos patas multi-leg simultáneas
VENTANA_RAFAGA_S = 1.0     # separación máxima entre trades de una ráfaga (un trozo)
FRACCION_ESTIMADO = 0.10   # un trozo es relevante desde esta fracción del premium_estimado

MULTI_LEG = {'MLET','MLAT','MLFT','MESL','MLCT','MFSL',
             'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}
STOCK_OPT = {'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}  # opciones + acciones
CANCELACIONES = {'CANC','CNCL','CNCO','CNOL'}  # anulan un trade anterior
ZONA_MUERTA = 0.25  # |agresividad| hasta aquí, frontera incluida = intención poco clara
# La agresividad se calcula en coma flotante: un trade justo en la frontera
# sale como 0.2499999... o como 0.2500000...3. La tolerancia la deja siempre
# en la zona muerta.
TOLERANCIA_ZONA_MUERTA = 1e-9

COMPRA, VENTA, INDETERMINADO = 'compra', 'venta', 'indeterminado'

# El CSV de nivel 2 debería traer siempre estos nombres de columna (ver el
# contrato de columnas de salida del pipeline). Esta tabla es un colchón de
# compatibilidad por si una corrida concreta escribió nombres distintos --
# no una licencia para no fijar el contrato aguas arriba.
ALIASES_COLUMNA = {
    'Time':            ['Time', 'tradeTime'],
    'Trade':           ['Trade', 'lastPrice'],
    'Trade Size':      ['Trade Size', 'tradeSize'],
    'Bid':             ['Bid', 'bidPrice'],
    'Ask':             ['Ask', 'askPrice'],
    'Trade Condition': ['Trade Condition', 'tradeConditionCode'],
    'Premium':         ['Premium', 'premium'],
}


def resolver_columnas(fieldnames):
    if fieldnames is None:
        # fichero sin ni siquiera cabecera
        fieldnames = []
    mapa, faltantes = {}, []
    for canonico, alias in ALIASES_COLUMNA.items():
        real = next((a for a in alias if a in fieldnames), None)
        if real is None:
            faltantes.append(f'{canonico} (probado: {alias})')
        else:
            mapa[canonico] = real
    if faltantes:
        raise ValueError(
            'El CSV de nivel 2 no tiene las columnas esperadas.\n'
            f'Columnas disponibles: {list(fieldnames)}\n'
            f'Faltan: {"; ".join(faltantes)}'
        )
    return mapa


def preparar_filas(filas, fieldnames):
    """
    Convierte filas crudas del CSV de nivel 2 (dicts de csv.DictReader) en
    filas de trade listas para agrupar: resuelve los alias de columna,
    descarta pies de página y filas sin hora, y añade los campos parseados
    't' (datetime), 'size' (int), 'premium' (float) y 'agr' (float o None).
    Modifica y devuelve los mismos dicts.
    """
    mapa = resolver_columnas(fieldnames)
    rows = []
    for r in filas:
        for canonico, real in mapa.items():
            if canonico not in r:
                r[canonico] = r[real]
        if r.get('es_metadata_footer') == 'True':
            continue
        if not r.get('Time'):
            continue
        r['t'] = datetime.strptime(r['Time'], '%Y-%m-%d %H:%M:%S.%f')
        r['size'] = int(float(r['Trade Size']))
        r['premium'] = float(r['Premium']) if r['Premium'] else 0.0
        r['agr'] = float(r['agresividad']) if r['agresividad'] else None
        rows.append(r)
    return rows


def lado(agr):
    """'compra' si agr > +ZONA_MUERTA, 'venta' si < -ZONA_MUERTA; None en medio, en la frontera o sin dato."""
    if agr is None or abs(agr) <= ZONA_MUERTA + TOLERANCIA_ZONA_MUERTA:
        return None
    return COMPRA if agr > 0 else VENTA


def cargar(path):
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return preparar_filas(reader, reader.fieldnames)


def quitar_cancelaciones(rows):
    """
    Una fila con condición de cancelación no es un trade: anula un trade
    anterior del mismo contrato, con el mismo precio y el mismo tamaño (el
    tape no dice cuál; se toma el más reciente que cuadre). Si se agruparan,
    contarían dos operaciones que no llegaron a ejecutarse. Se quitan las dos
    filas antes de agrupar.

    Devuelve (filas que quedan, [(cancelación, trade anulado o None)]); None
    si no se encuentra el trade anulado (por ejemplo, porque se negoció
    fuera de la ventana capturada): la cancelación se quita igualmente.
    """
    cancelaciones = sorted((r for r in rows if r['Trade Condition'] in CANCELACIONES),
                           key=lambda r: r['t'])
    if not cancelaciones:
        return rows, []
    quitar = {id(c) for c in cancelaciones}
    pares = []
    for c in cancelaciones:
        candidatos = [r for r in rows
                      if id(r) not in quitar
                      and r['contract_symbol'] == c['contract_symbol']
                      and r['size'] == c['size']
                      and float(r['Trade']) == float(c['Trade'])
                      and r['t'] <= c['t']]
        anulado = max(candidatos, key=lambda r: r['t']) if candidatos else None
        if anulado is not None:
            quitar.add(id(anulado))
        pares.append((c, anulado))
    return [r for r in rows if id(r) not in quitar], pares


class UF:
    def __init__(s, n): s.p = list(range(n))
    def find(s, x):
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def union(s, a, b):
        ra, rb = s.find(a), s.find(b)
        if ra != rb: s.p[rb] = ra


def agrupar(rows, precios=None, estimados=None):
    """
    Agrupa las filas en operaciones: {raíz: [filas]}. `precios` es el precio
    de cada subyacente y `estimados` el premium_estimado de cada contrato,
    ambos del nivel 1 de la captura (ver cargar_nivel1); sin ellos, todos
    los trozos son relevantes. Anota en cada fila de una pata su trozo
    ('trozo') y el lado del trozo ('lado_trozo'), que usa resumen().
    """
    uf = UF(len(rows))
    multi_leg = [i for i, r in enumerate(rows) if r['Trade Condition'] in MULTI_LEG]
    una_pata = [i for i, r in enumerate(rows) if r['Trade Condition'] not in MULTI_LEG]
    _unir_multi_leg(rows, multi_leg, uf)
    _unir_una_pata(rows, una_pata, uf, precios or {}, estimados or {})

    grupos = collections.defaultdict(list)
    for i in range(len(rows)):
        grupos[uf.find(i)].append(rows[i])
    return grupos


def _unir_multi_leg(rows, idxs_multi_leg, uf):
    por_sym = collections.defaultdict(list)
    for i in idxs_multi_leg:
        por_sym[rows[i]['symbol']].append(i)

    # A) patas simultáneas en contratos distintos del mismo subyacente,
    #    Y con la misma Trade Condition (una orden multi-leg imprime
    #    todas sus patas bajo el mismo código de mecanismo de ejecución;
    #    exigirlo evita encadenar prints de mecanismos distintos que
    #    solo coinciden en milisegundo por casualidad de mercado)
    for sym, idxs in por_sym.items():
        idxs.sort(key=lambda i: rows[i]['t'])
        for a in range(len(idxs)):
            ia = idxs[a]
            for b in range(a + 1, len(idxs)):
                ib = idxs[b]
                dt = (rows[ib]['t'] - rows[ia]['t']).total_seconds()
                if dt > TOL_MS / 1000.0:
                    break
                if (rows[ia]['contract_symbol'] != rows[ib]['contract_symbol']
                        and rows[ia]['Trade Condition'] == rows[ib]['Trade Condition']):
                    uf.union(ia, ib)

    # B) troceado dentro del mismo contrato + misma condición
    por_clave = collections.defaultdict(list)
    for i in idxs_multi_leg:
        por_clave[(rows[i]['contract_symbol'], rows[i]['Trade Condition'])].append(i)
    for idxs in por_clave.values():
        idxs.sort(key=lambda i: rows[i]['t'])
        for j in range(1, len(idxs)):
            if (rows[idxs[j]]['t'] - rows[idxs[j-1]]['t']).total_seconds() <= VENTANA_S:
                uf.union(idxs[j-1], idxs[j])


def umbral_trozo(precio, estimado):
    """
    Premium desde el que un trozo es relevante: el menor entre el umbral del
    subyacente y FRACCION_ESTIMADO del premium_estimado del contrato; sin
    estimado, FRACCION_ESTIMADO del umbral. Sin precio, None: todos los
    trozos son relevantes, igual que pasa_umbral() no descarta sin precio.
    """
    if precio is None:
        return None
    umbral = umbral_premium(precio)
    if estimado is not None and estimado > 0:
        return min(umbral, FRACCION_ESTIMADO * estimado)
    return FRACCION_ESTIMADO * umbral


def _rafagas(rows, idxs):
    """Trozos de un contrato y condición: [(lado, [índices])], por lado y con VENTANA_RAFAGA_S entre trades."""
    por_lado = collections.defaultdict(list)
    for i in idxs:
        por_lado[lado(rows[i]['agr'])].append(i)
    trozos = []
    for l, del_lado in por_lado.items():
        del_lado.sort(key=lambda i: (rows[i]['t'], i))
        actual = [del_lado[0]]
        for i in del_lado[1:]:
            if (rows[i]['t'] - rows[actual[-1]]['t']).total_seconds() <= VENTANA_RAFAGA_S:
                actual.append(i)
            else:
                trozos.append((l, actual))
                actual = [i]
        trozos.append((l, actual))
    return trozos


def _unir_una_pata(rows, idxs_una_pata, uf, precios, estimados):
    por_clave = collections.defaultdict(list)
    for i in idxs_una_pata:
        por_clave[(rows[i]['contract_symbol'], rows[i]['Trade Condition'])].append(i)
    n_trozo = 0
    for (contrato, _), idxs in por_clave.items():
        minimo = umbral_trozo(precios.get(rows[idxs[0]]['symbol']), estimados.get(contrato))
        relevantes = []
        for l, trozo in _rafagas(rows, idxs):
            n_trozo += 1
            for i in trozo:
                rows[i]['trozo'] = n_trozo
                rows[i]['lado_trozo'] = l
                uf.union(trozo[0], i)
            if minimo is None or sum(rows[i]['premium'] for i in trozo) >= minimo:
                relevantes.append((l, trozo))

        # encadenado: una sola operación en curso por contrato y condición
        relevantes.sort(key=lambda c: (rows[c[1][0]]['t'], c[1][0]))
        en_curso = None   # (primer índice, lado, último trade)
        for l, trozo in relevantes:
            inicio, fin = rows[trozo[0]]['t'], max(rows[i]['t'] for i in trozo)
            if (en_curso is not None
                    and (inicio - en_curso[2]).total_seconds() <= VENTANA_S
                    and (l is None or en_curso[1] is None or l == en_curso[1])):
                uf.union(en_curso[0], trozo[0])
                en_curso = (en_curso[0], en_curso[1] or l, max(en_curso[2], fin))
            else:
                en_curso = (trozo[0], l, fin)


def direccion(tipo, agr):
    """Traduce agresividad + tipo de contrato a sesgo direccional."""
    return direccion_de_lado(tipo, lado(agr))


def direccion_de_lado(tipo, l):
    """Sesgo direccional de comprar o vender un contrato: comprar call o vender put es alcista."""
    if l is None:
        return INDETERMINADO
    comprador = l == COMPRA
    if tipo.lower().startswith('c'):
        return 'bull' if comprador else 'bear'
    return 'bear' if comprador else 'bull'


def estructura(patas):
    """Infiere la estructura a partir de los contratos implicados."""
    if len(patas) == 1:
        return f"single_leg_{patas[0]['type'].lower()}"
    exps = {p['exp_date'] for p in patas}
    tipos = {p['type'] for p in patas}
    strikes = {p['strike'] for p in patas}
    if len(exps) > 1:
        return 'calendar/diagonal'
    if len(tipos) > 1:
        return 'straddle/strangle/risk-reversal' if len(strikes) > 1 else 'straddle'
    return 'vertical'


def precio_neto_operacion(filas_pata, patas_incompletas):
    """
    SL (1 pata, un solo trade o varios troceados del mismo individuo):
      precio medio ponderado por tamaño de esa pata, sin más.
    ML (2+ patas, todas capturadas):
      suma con signo del precio medio de cada pata: +precio si esa pata
      se compró (agresividad>0, agresor al ask), -precio si se vendió
      (agresividad<0, agresor al bid). Una vertical/bull call queda como
      precio_call_comprada - precio_call_vendida, tal como se pidió;
      se generaliza igual a más de 2 patas (crédito/débito neto total).
    Si patas_incompletas, o si alguna pata no tiene dirección clara
    (agresividad en zona muerta o sin dato), no se calcula -- no tiene
    sentido combinar precios sin saber qué lado se compró y cuál se
    vendió, y mejor dejarlo vacío que adivinar.
    """
    if patas_incompletas:
        return '', 'no_calculable_patas_incompletas'
    if len(filas_pata) == 1:
        return round(filas_pata[0]['precio_medio'], 4), 'single_leg'
    for p in filas_pata:
        if lado(p['agr']) is None:
            return '', 'no_calculable_direccion_ambigua'
    neto = sum((p['precio_medio'] if p['agr'] > 0 else -p['precio_medio'])
               for p in filas_pata)
    return round(neto, 4), 'multi_leg_combinado'


def _fmt_strike(x):
    s = f'{x:.2f}'
    return s.rstrip('0').rstrip('.') if '.' in s else s


def resumen_pata(contract_symbol, rs):
    """
    Cálculo por pata: agrega las filas de un mismo contrato dentro de una
    operación. La agresividad de la pata es la media ponderada por tamaño
    de las filas que la tienen (None si ninguna la tiene).
    """
    size = sum(r['size'] for r in rs)
    prem = sum(r['premium'] for r in rs)
    con_agr = [r for r in rs if r['agr'] is not None]
    agr = (sum(r['agr'] * r['size'] for r in con_agr) /
           sum(r['size'] for r in con_agr)) if con_agr else None
    precio_medio = sum(float(r['Trade']) * r['size'] for r in rs) / size
    return {
        'contract_symbol': contract_symbol, 'type': rs[0]['type'],
        'strike': rs[0]['strike'], 'exp_date': rs[0]['exp_date'],
        'n_trades': len(rs), 'size': size, 'premium': prem, 'agr': agr,
        'precio_medio': precio_medio,
    }


def patas_de(grupo):
    """Detalle por pata de una operación, de mayor a menor premium."""
    patas = collections.defaultdict(list)
    for r in grupo:
        patas[r['contract_symbol']].append(r)
    filas_pata = [resumen_pata(cs, rs) for cs, rs in patas.items()]
    filas_pata.sort(key=lambda p: -p['premium'])
    return filas_pata


def trozos_de(grupo):
    """
    Trozos de una operación de una pata, por orden de inicio: [(lado,
    premium)]. Lista vacía si la operación es multi-leg (sus filas no se
    trocean).
    """
    por_trozo = collections.defaultdict(list)
    for r in grupo:
        if 'trozo' in r:
            por_trozo[r['trozo']].append(r)
    trozos = sorted(por_trozo.values(), key=lambda rs: min(r['t'] for r in rs))
    return [(rs[0]['lado_trozo'], sum(r['premium'] for r in rs)) for rs in trozos]


def _campos_trozos(grupo):
    """Lado de la operación, nº de trozos, premium del mayor y si el lado sale de un trozo menor."""
    trozos = trozos_de(grupo)
    if not trozos:
        return {'lado': '', 'n_trozos': '', 'premium_trozo_mayor': '', 'lado_de_trozo_menor': ''}
    lado_op = next((l for l, _ in trozos if l is not None), None)
    mayor = max(trozos, key=lambda t: t[1])
    return {
        'lado': lado_op or INDETERMINADO,
        'n_trozos': len(trozos),
        'premium_trozo_mayor': round(mayor[1], 2),
        'lado_de_trozo_menor': mayor[0] is None and lado_op is not None,
    }


def id_operacion(grupo):
    """
    ID estable de la operación: fecha, subyacente, hora con milisegundos y
    Trade Condition del primer trade del grupo,
    'YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC'.

    La Trade Condition es necesaria: dos grupos distintos pueden empezar en
    el mismo milisegundo y el mismo contrato con condiciones distintas (p. ej.
    AUTO e ISOI). La agrupación solo une filas de la misma condición, así que
    todas las filas de un grupo la comparten. En las condiciones multi-leg,
    dos grupos con el mismo subyacente, milisegundo y condición ya habrían
    quedado unidos; en las de una pata no (contratos o lados distintos), y
    ids_operaciones() deshace esas coincidencias.
    """
    primero = min(grupo, key=lambda r: r['t'])
    return '{}-{}-{}-{}'.format(
        primero['t'].strftime('%Y%m%d'), primero['symbol'],
        primero['t'].strftime('%H:%M:%S.%f')[:-3], primero['Trade Condition'])


def _sufijo_id(grupo):
    """Contrato y lado de una operación de una pata: '20261120-185C-venta'."""
    pata = patas_de(grupo)[0]
    tipo = 'C' if pata['type'].lower().startswith('c') else 'P'
    lado_op = _campos_trozos(grupo)['lado'] or INDETERMINADO
    return f"{pata['exp_date'].replace('-', '')}-{_fmt_strike(float(pata['strike']))}{tipo}-{lado_op}"


def ids_operaciones(grupos):
    """
    ID único de cada operación de la captura: {raíz: ID}.

    Con la regla de una pata, dos operaciones pueden empezar en el mismo
    milisegundo con el mismo subyacente y Trade Condition (una compra y una
    venta del mismo contrato, o dos contratos distintos) y tener el mismo
    id_operacion(). Entonces la de mayor premium conserva ese ID (es la que
    tenía con la regla anterior en casi todos los casos) y las demás añaden
    su contrato y su lado, que dependen solo del contenido: el ID sigue
    siendo estable entre capturas.
    """
    por_id = collections.defaultdict(list)
    for raiz, grupo in grupos.items():
        por_id[id_operacion(grupo)].append(raiz)
    ids = {}
    for base, raices in por_id.items():
        orden = sorted(raices, key=lambda r: (-sum(f['premium'] for f in grupos[r]), _sufijo_id(grupos[r])))
        ids[orden[0]] = base
        for raiz in orden[1:]:
            ids[raiz] = f'{base}-{_sufijo_id(grupos[raiz])}'
    return ids


def resumen(grupo):
    filas_pata = patas_de(grupo)

    total_prem = sum(p['premium'] for p in filas_pata)
    total_size = sum(p['size'] for p in filas_pata)
    con_agr = [p for p in filas_pata if p['agr'] is not None]
    agr_pond = (sum(p['agr'] * p['size'] for p in con_agr) /
                sum(p['size'] for p in con_agr)) if con_agr else None

    cond = collections.Counter(r['Trade Condition'] for r in grupo)
    ts = [r['t'] for r in grupo]
    dom = filas_pata[0]
    patas_incompletas = (any(r['Trade Condition'] in MULTI_LEG for r in grupo)
                          and len(filas_pata) == 1)
    precio_neto, precio_neto_metodo = precio_neto_operacion(filas_pata, patas_incompletas)
    trozos = _campos_trozos(grupo)
    # una operación de una pata tiene el lado con el que se construyó
    sesgo = (direccion_de_lado(dom['type'], _lado_operacion(trozos)) if trozos['lado']
             else direccion(dom['type'], dom['agr']))

    # Strike: un valor si todas las patas comparten strike (incluye calendars
    # puros); "x-y" si hay dos strikes distintos (vertical/diagonal); lista
    # por comas si hay más de dos (butterfly, iron condor, etc.)
    strikes_unicos = sorted(set(float(p['strike']) for p in filas_pata))
    if len(strikes_unicos) == 1:
        strike_fmt = _fmt_strike(strikes_unicos[0])
    elif len(strikes_unicos) == 2:
        strike_fmt = f'{_fmt_strike(strikes_unicos[0])}-{_fmt_strike(strikes_unicos[1])}'
    else:
        strike_fmt = ','.join(_fmt_strike(s) for s in strikes_unicos)

    # Fecha de expiración: un valor si todas comparten fecha (vertical,
    # straddle/strangle); "fecha_cercana→fecha_lejana" si hay dos (calendar/
    # diagonal, orden cronológico deja claro cuál es la pata corta y cuál la
    # larga); lista por comas si hay más de dos
    exps_unicas = sorted(set(p['exp_date'] for p in filas_pata))
    if len(exps_unicas) == 1:
        exp_fmt = exps_unicas[0]
    elif len(exps_unicas) == 2:
        exp_fmt = f'{exps_unicas[0]}→{exps_unicas[1]}'
    else:
        exp_fmt = ','.join(exps_unicas)

    # Fecha en la que ocurrió la operación (día/mes; normalmente una sola,
    # pero puede haber más de una si el grupo cruza fechas)
    fechas_operacion = sorted(set(r['t'].strftime('%d/%m') for r in grupo))
    fecha_operacion_fmt = ','.join(fechas_operacion)

    return {
        'symbol': grupo[0]['symbol'],
        'estructura': estructura(filas_pata),
        'n_patas': len(filas_pata),
        'n_trades': len(grupo),
        'size_total': total_size,
        'premium_total': round(total_prem, 2),
        'precio_neto': precio_neto,
        'precio_neto_metodo': precio_neto_metodo,
        'agresividad_pond': round(agr_pond, 3) if agr_pond is not None else '',
        'direccion': sesgo,
        'trade_conditions': '|'.join(f'{c}x{n}' for c, n in cond.most_common()),
        'multi_leg_declarado': any(r['Trade Condition'] in MULTI_LEG for r in grupo),
        'patas_incompletas': patas_incompletas,
        'stock_option': any(r['Trade Condition'] in STOCK_OPT for r in grupo),
        'hora_inicio': min(ts).strftime('%H:%M:%S.%f')[:-3],
        'hora_fin': max(ts).strftime('%H:%M:%S.%f')[:-3],
        'duracion_s': round((max(ts) - min(ts)).total_seconds(), 3),
        'strike': strike_fmt,
        'fecha_expiracion': exp_fmt,
        'fecha_operacion': fecha_operacion_fmt,
        **trozos,
    }


def _lado_operacion(campos_trozos):
    return None if campos_trozos['lado'] == INDETERMINADO else campos_trozos['lado']


def resumir_todas(grupos):
    """Resumen de cada grupo, ordenados por premium total descendente."""
    return sorted((resumen(g) for g in grupos.values()),
                  key=lambda o: -o['premium_total'])


def umbral_premium(precio):
    if 1 <= precio < 50:
        return 500_000
    if 50 <= precio < 200:
        return 1_000_000
    return 3_000_000


def pasa_umbral(premium_total, precio):
    """
    True si el premium (en dólares) alcanza el umbral del tramo de precio.
    Sin precio no se descarta: no debería pasar (todo símbolo de nivel 2
    viene de nivel 1), pero si pasa, no se descarta a ciegas por falta de
    precio.
    """
    if precio is None:
        return True
    return premium_total >= umbral_premium(precio)


def filtrar_por_umbral(todas, precios):
    """Separa las operaciones que superan el umbral; devuelve (ops, nº descartadas)."""
    ops, descartadas = [], 0
    for o in todas:
        if pasa_umbral(o['premium_total'], precios.get(o['symbol'])):
            ops.append(o)
        else:
            descartadas += 1
    return ops, descartadas


def cargar_precios(path_nivel1):
    return cargar_nivel1(path_nivel1)[0]


def _contrato_nivel1(r):
    """
    Contrato de una fila de nivel 1 con el formato del nivel 2
    ('SIMBOLO|AAAAMMDD|STRIKE.00C'). Algunos nivel 1 antiguos no traen la
    columna: se reconstruye igual que lo hace el dashboard. None si no se puede.
    """
    contrato = r.get('contract_symbol') or r.get('option_symbol')
    if contrato:
        return contrato
    try:
        tipo = 'C' if r['type'].lower().startswith('c') else 'P'
        return f"{r['symbol']}|{r['exp_date'].replace('-', '')}|{float(r['strike']):.2f}{tipo}"
    except (KeyError, ValueError, AttributeError):
        return None


def cargar_nivel1(path_nivel1):
    """Precio de cada subyacente y premium_estimado de cada contrato del nivel 1: (precios, estimados)."""
    precios, estimados = {}, {}
    with open(path_nivel1, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            precios.setdefault(r['symbol'], float(r['price']))
            contrato = _contrato_nivel1(r)
            if contrato and r.get('premium_estimado'):
                estimados.setdefault(contrato, float(r['premium_estimado']))
    return precios, estimados


def escribir_operaciones(salida, todas, ops):
    """Escribe nivel3_operaciones con los premiums en millones (solo presentación)."""
    en_millones = ('premium_total', 'premium_trozo_mayor')
    campos = [c + '_M' if c in en_millones else c for c in todas[0].keys()]
    filas_salida = []
    for o in ops:
        fila = {}
        for c, v in o.items():
            if c in en_millones:
                fila[c + '_M'] = round(v / 1_000_000, 3) if v != '' else ''
            else:
                fila[c] = v
        filas_salida.append(fila)

    with open(salida, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas_salida)


def main(entrada, path_nivel1, salida):
    rows, cancelaciones = quitar_cancelaciones(cargar(entrada))
    if not rows:
        raise ValueError(
            f'El CSV de nivel 2 no tiene ningún trade: {entrada}\n'
            'No se genera el nivel 3 de este día.'
        )
    precios, estimados = cargar_nivel1(path_nivel1)
    grupos = agrupar(rows, precios, estimados)
    todas = resumir_todas(grupos)
    ops, descartadas = filtrar_por_umbral(todas, precios)

    escribir_operaciones(salida, todas, ops)
    return rows, todas, ops, descartadas, cancelaciones


if __name__ == '__main__':
    rows, todas, ops, descartadas, cancelaciones = main(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f'{len(rows)} trades -> {len(todas)} operaciones agrupadas -> '
          f'{len(ops)} tras el umbral de premium ({descartadas} descartadas)')
    if cancelaciones:
        sin_anulado = sum(1 for _, anulado in cancelaciones if anulado is None)
        print(f'{len(cancelaciones)} cancelaciones quitadas junto con el trade que anulan'
              + (f' ({sin_anulado} sin trade anulado localizado)' if sin_anulado else ''))
