# 0020. Las multi-legs se corrigen eligiendo el tipo de operación

- **Fecha:** 2026-10-19
- **Estado:** aceptada (amplía 0011 a la pestaña 1)

## Contexto

En muchas multi-legs no se puede saber de la agresividad qué pata se compró: alguna pata cae en la zona muerta, las dos salen del mismo lado (en los datos reales hay verticales y diagonales «compra-compra» y «venta-venta») o la agrupación es dudosa. En una multi-leg, corregir solo «bull/bear», como dice la especificación para las single-leg, no basta para saber el lado de cada pata ni el destino.

## Decisión

- En la pestaña 1, una multi-leg se corrige con el mismo **selector de tipo de operación** de la pestaña 2 ([0011](0011-pata-manual-tipo-de-operacion.md)): bull call, bear put, straddle, «no lo sé»… El tipo fija el lado de cada pata.
- Mientras no se corrija, una vertical o diagonal con alguna pata indeterminada, o con **las dos patas del mismo lado**, va a **indeterminadas multi-leg**.
- Las single-leg se siguen corrigiendo con bull, bear o indeterminado.

## Alternativas descartadas

- **Solo bull/bear en multi-legs**: el destino quedaría aproximado.
- **Multi-legs no editables**: dejaría sin remedio las agrupaciones dudosas.

## Consecuencias

Las reglas y el catálogo están en [reglas de negocio](../reglas-negocio.md#correcciones-manuales).
