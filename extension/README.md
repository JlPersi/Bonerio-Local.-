# Bonerío Inside (prototipo)

Extensión de Chrome que muestra, al lado de Matriz, los datos de Bonerío Local para el bono que tenés abierto:
TIR al cierre, TIR estimada al precio de la pantalla o de la boleta, duration, días al vencimiento y un semáforo contra la curva
(TIR = a + b·ln(días) dentro del grupo, con la misma ley si alcanza; ±25 pb = en línea).

- El precio sale de la pantalla del usuario (boleta, «Cierre» o «Cierre Ant.» del recuadro del bono). Bonerío solo pone `data/api/curvas.json`: nada en vivo de Primary.
- El ticker se toma de la boleta, del título del recuadro del bono o de la fila donde hacés clic. No usa clases de Matriz, porque cambian.
- La TIR a otro precio se estima con la duration (ΔTIR ≈ −ΔP/P / MD), sin convexidad.

## Instalar para probar
1. `chrome://extensions` → activar «Modo de desarrollador» → «Cargar descomprimida» → elegir esta carpeta `extension/`.
2. Entrar a Matriz. Si el panel no aparece solo (dominio distinto), hacer clic en el ícono de la extensión.
