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
"""

import csv, sys, collections
from datetime import datetime

VENTANA_S = 120.0   # separación máxima entre trades del mismo contrato
TOL_MS    = 50      # tolerancia para considerar dos patas simultáneas

MULTI_LEG = {'MLET','MLAT','MLFT','MESL','MLCT','MFSL',
             'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}
STOCK_OPT = {'TLET','TLAT','TLCT','TLFT','TASL','TESL','TFSL'}  # opciones + acciones
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


def cargar(path):
    rows = []
    reader = csv.DictReader(open(path))
    mapa = resolver_columnas(reader.fieldnames)
    for r in reader:
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


def resumen(grupo):
    patas = collections.defaultdict(list)
    for r in grupo:
        patas[r['contract_symbol']].append(r)

    filas_pata = []
    for cs, rs in patas.items():
        size = sum(r['size'] for r in rs)
        prem = sum(r['premium'] for r in rs)
        con_agr = [r for r in rs if r['agr'] is not None]
        agr = (sum(r['agr'] * r['size'] for r in con_agr) /
               sum(r['size'] for r in con_agr)) if con_agr else None
        precio_medio = sum(float(r['Trade']) * r['size'] for r in rs) / size
        filas_pata.append({
            'contract_symbol': cs, 'type': rs[0]['type'],
            'strike': rs[0]['strike'], 'exp_date': rs[0]['exp_date'],
            'n_trades': len(rs), 'size': size, 'premium': prem, 'agr': agr,
            'precio_medio': precio_medio,
        })
    filas_pata.sort(key=lambda p: -p['premium'])

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
        exp_fmt = f'{exps_unicas[0]}\u2192{exps_unicas[1]}'
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


def umbral_premium(precio):
    if 1 <= precio < 50:
        return 500_000
    if 50 <= precio < 200:
        return 1_000_000
    return 3_000_000


def cargar_precios(path_nivel1):
    precios = {}
    for r in csv.DictReader(open(path_nivel1)):
        precios.setdefault(r['symbol'], float(r['price']))
    return precios


def main(entrada, path_nivel1, salida):
    rows = cargar(entrada)
    grupos = agrupar(rows)
    todas = sorted((resumen(g) for g in grupos.values()),
                    key=lambda o: -o['premium_total'])

    precios = cargar_precios(path_nivel1)
    ops, descartadas = [], 0
    for o in todas:
        precio = precios.get(o['symbol'])
        if precio is None:
            # no debería pasar (todo símbolo de nivel 2 viene de nivel 1),
            # pero si pasa, no se descarta a ciegas por falta de precio
            ops.append(o)
        elif o['premium_total'] >= umbral_premium(precio):
            ops.append(o)
        else:
            descartadas += 1

    campos = [c if c != 'premium_total' else 'premium_total_M' for c in todas[0].keys()]
    filas_salida = []
    for o in ops:
        fila = dict(o)
        fila['premium_total_M'] = round(fila.pop('premium_total') / 1_000_000, 3)
        filas_salida.append(fila)

    with open(salida, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas_salida)
    return rows, todas, ops, descartadas


if __name__ == '__main__':
    rows, todas, ops, descartadas = main(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f'{len(rows)} trades -> {len(todas)} operaciones agrupadas -> '
          f'{len(ops)} tras el umbral de premium ({descartadas} descartadas)')
