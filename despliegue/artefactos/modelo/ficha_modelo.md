# Ficha del modelo score_libranza v20261115

- Modelo: M2, regresión logística con penalización L2 (C = 0,1), elegida por la regla preespecificada de la tesis v2.
- Población: créditos de libranza; la API rechaza otros productos.
- Evento: 90 o más días de mora en los 12 meses desde el desembolso.
- Entrenamiento: 733 créditos y 23 incumplimientos (2022-2026), sin Home Credit.
- Validación cruzada agrupada 5 x 20: AUC 0.629; log loss 0.1387 (tasa base 0,1396); pendiente 0.62.
- La mejora frente a la tasa base no es demostrable; uso previsto: apoyo al analista por bandas, no rechazo automático.
- Bandas (PD): A < 0.0157 ≤ B < 0.0314 ≤ C < 0.0628 ≤ D < 0.1255 ≤ E.
- Reemplaza al modelo v20261107 (tesis v1), guardado en artefactos/_v20261107.
- Huella SHA-256 de modelo.json: c2bcc7f68f149f68
- Ficha completa: 07_tesis_v2/resultados/fase4/ficha_modelo_v2.md
