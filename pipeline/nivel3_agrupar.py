#!/usr/bin/env python3
"""
Nivel 3 — Agrupa las filas de Time & Sales (nivel 2) en operaciones que
parecen pertenecer al mismo actor.

Dos mecanismos de agrupación:

  A) Cruce entre contratos (patas de una misma orden multi-leg):
     filas de contratos DISTINTOS del mismo subyacente ejecutadas
     prácticamente en el mismo instante (<= TOL_MS). Una orden multi-leg
     se imprime en el tape con el mismo timestamp para todas sus patas.

  B) Troceado dentro del mismo contrato:
     filas del MISMO contrato, con la MISMA Trade Condition, separadas
     por menos de VENTANA_S segundos. Es el criterio manual del usuario
     ("mismo trade condition y pocos minutos entre trades").

Las dos se combinan: si un grupo del tipo B toca un cruce del tipo A,
todo queda en la misma operación (union-find).

Uso por línea de comandos, como lo ejecuta el pipeline (sin cambios respecto a
versiones anteriores):

  python3 nivel3_agrupar.py nivel2_trades_YYYYMMDD.csv \
      nivel1_candidatos_YYYYMMDD.csv nivel3_operaciones_YYYYMMDD.csv

Uso como módulo (dashboard). Las piezas que componen main() se pueden
llamar por separado, para agrupar y aplicar ediciones manuales antes de
filtrar por umbral:

  preparar_filas(filas, fieldnames) -> filas de trade listas para agrupar
  quitar_cancelaciones(rows)        -> (filas sin cancelaciones ni trades anulados, pares)
  agrupar(rows)                     -> {raíz: [filas]} (un grupo = una operación)
  patas_de(grupo)                   -> detalle por pata (resumen_pata de cada contrato)
  resumen(grupo)                    -> fila de nivel3_operaciones (premium en $)
  id_operacion(grupo)               -> 'YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC'
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
"""

import csv, sys, collections
from datetime import datetime

VENTANA_S = 120.0   # separación máxima entre trades del mismo contrato
TOL_MS    = 50      # tolerancia para considerar dos patas simultáneas

MULTI_LEG = {'MLET','MLAT','MLFT','MESL','MLCT','MFSL',
             'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}
STOCK_OPT = {'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}  # opciones + acciones
CANCELACIONES = {'CANC','CNCL','CNCO','CNOL'}  # anulan un trade anterior
ZONA_MUERTA = 0.25  # |agresividad| por debajo = intención poco clara

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


def agrupar(rows):
    uf = UF(len(rows))
    por_sym = collections.defaultdict(list)
    for i, r in enumerate(rows):
        por_sym[r['symbol']].append(i)

    # A) patas simultáneas en contratos distintos del mismo subyacente,
    #    Y con la misma Trade Condition (una orden multi-leg imprime
    #    todas sus patas bajo el mismo código de mecanismo de ejecución;
    #    exigirlo evita encadenar prints de mecanismos distintos que
    #    solo coinciden en milisegundo por casualidad de mercado)
    cruces = set()
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
                    cruces.add(uf.find(ia))

    # B) troceado dentro del mismo contrato + misma condición
    por_clave = collections.defaultdict(list)
    for i, r in enumerate(rows):
        por_clave[(r['contract_symbol'], r['Trade Condition'])].append(i)
    for idxs in por_clave.values():
        idxs.sort(key=lambda i: rows[i]['t'])
        for j in range(1, len(idxs)):
            if (rows[idxs[j]]['t'] - rows[idxs[j-1]]['t']).total_seconds() <= VENTANA_S:
                uf.union(idxs[j-1], idxs[j])

    grupos = collections.defaultdict(list)
    for i in range(len(rows)):
        grupos[uf.find(i)].append(rows[i])
    return grupos


def direccion(tipo, agr):
    """Traduce agresividad + tipo de contrato a sesgo direccional."""
    if agr is None or abs(agr) < ZONA_MUERTA:
        return 'indeterminado'
    comprador = agr > 0
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
        if p['agr'] is None or abs(p['agr']) < ZONA_MUERTA:
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


def id_operacion(grupo):
    """
    ID estable de la operación: fecha, subyacente, hora con milisegundos y
    Trade Condition del primer trade del grupo,
    'YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC'.

    La Trade Condition es necesaria: dos grupos distintos pueden empezar en
    el mismo milisegundo y el mismo contrato con condiciones distintas (p. ej.
    AUTO e ISOI). Con ella el ID es único dentro de una captura: los dos
    mecanismos de agrupación solo unen filas de la misma condición, así que
    todas las filas de un grupo la comparten, y dos grupos con el mismo
    subyacente, milisegundo y condición ya habrían quedado unidos.
    """
    primero = min(grupo, key=lambda r: r['t'])
    return '{}-{}-{}-{}'.format(
        primero['t'].strftime('%Y%m%d'), primero['symbol'],
        primero['t'].strftime('%H:%M:%S.%f')[:-3], primero['Trade Condition'])


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
        'direccion': direccion(dom['type'], dom['agr']),
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
    }


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
    precios = {}
    with open(path_nivel1, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            precios.setdefault(r['symbol'], float(r['price']))
    return precios


def escribir_operaciones(salida, todas, ops):
    """Escribe nivel3_operaciones con el premium en millones (solo presentación)."""
    campos = [c if c != 'premium_total' else 'premium_total_M' for c in todas[0].keys()]
    filas_salida = []
    for o in ops:
        fila = dict(o)
        fila['premium_total_M'] = round(fila.pop('premium_total') / 1_000_000, 3)
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
    grupos = agrupar(rows)
    todas = resumir_todas(grupos)

    precios = cargar_precios(path_nivel1)
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
