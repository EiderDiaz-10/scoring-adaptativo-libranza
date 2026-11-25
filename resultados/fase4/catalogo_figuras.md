# Figuras de la Fase 4

| Código | Archivo | Mensaje |
|---|---|---|
| M01 | `figuras/fase4/M01_comparacion_modelos.png` | Ningún modelo mejora de forma demostrable a la tasa base en log loss; los mejores discriminan (AUC 0,63–0,65, límite inferior ≥ 0,50) y la regla de políticas va al revés. |
| M02 | `figuras/fase4/M02_calibracion.png` | Las bandas de calibración son muy anchas por encima del 5 % de PD: con 23 eventos solo se puede verificar la calibración en el rango bajo. |
| M03 | `figuras/fase4/M03_curva_decision.png` | Solo entre umbrales de 3 % y 6 % los modelos superan a aprobar o rechazar a todos (hasta ≈ 8 por 1.000); por encima de 7 % no aportan. |
| M04 | `figuras/fase4/M04_coeficientes_M2_M3.png` | Ningún coeficiente excluye el 0; empleador, antigüedad, edad y monto son las señales más consistentes, y el prior desplaza la historia del cliente sin cambiar la conclusión. |
| M05 | `figuras/fase4/M05_shap_M5.png` | El boosting usa solo cinco variables (empleador, antigüedad, plazo, edad y monto), con efectos monótonos y sin interacciones. |
| M06 | `figuras/fase4/M06_cox_hazard_ratios.png` | En Cox solo dos variables son significativas: la experiencia del empleador protege (HR 0,56) y, contra la hipótesis, también el plazo largo (HR 0,44). |
| M07 | `figuras/fase4/M07_curvas_tau_peso_hc.png` | El log loss es mínimo en τ = 0,25 con ambos centros; por debajo, el centro Home Credit empeora porque impone direcciones que FINTECH no respalda. Apilar más Home Credit mejora M4 sin alcanzar a M3. |
| M08 | `figuras/fase4/M08_estabilidad_seleccion.png` | Con el C elegido, empleador, monto y edad entran en más del 80 % de las réplicas; con más penalización solo sobrevive el empleador. |
| M09 | `figuras/fase4/M09_inferencia_rechazados.png` | La aumentación con rechazados apenas cambia la discriminación en aprobados; los coeficientes se contraen y la PD de la población que solicita sube solo bajo el supuesto k. |
| M10 | `figuras/fase4/M10_backtest_temporal.png` | En 2025+ ningún modelo discrimina (AUC 0,37–0,59, con IC que cubren casi todo el rango) ni mejora a la tasa base: el AUC de 0,63 de la validación cruzada no se sostiene en el tiempo. |
| M11 | `figuras/fase4/M11_backtest_captura_calibracion.png` | En 2025+, M2, M3 y la regla capturan 2 de los 5 incumplimientos en el 15 % de mayor PD, pero los otros 3 quedan al fondo del ordenamiento; todos los modelos sobrestiman la PD (2,3–5,3 % frente a 2,1 % observada), aunque solo M6 sale del IC de la tasa observada. |
| M12 | `figuras/fase4/M12_auc_univariado_por_cohorte.png` | Ningún predictor mantiene una relación estable con el incumplimiento entre cohortes: el monto, la señal más regular antes de 2025, se invierte en 2025+. |
