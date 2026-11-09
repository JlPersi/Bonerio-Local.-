# Bonerío Inside (prototipo)

**Bonerío entero al costado de Matriz:** el ícono de la extensión abre boneriolocal.com.ar en el panel lateral de Chrome, con el mismo menú y la misma cuenta.
Los botones *Ficha*, *Curva* y *Portfolio* del panel flotante lo abren directo en el bono que estás mirando (usan los links `#ficha=TMVE8` y `#tab=dsim` de la página).

Extensión de Chrome que muestra, al lado de Matriz, los datos de Bonerío Local para el bono que tenés abierto:
TIR al cierre, TIR estimada al precio de la pantalla o de la boleta, duration, días al vencimiento y un semáforo contra la curva
(TIR = a + b·ln(días) dentro del grupo, con la misma ley si alcanza; ±25 pb = en línea).

- El precio sale de la pantalla del usuario (boleta, «Cierre» o «Cierre Ant.» del recuadro del bono). Bonerío solo pone `data/api/curvas.json`: nada en vivo de Primary.
- El ticker se toma de la boleta, del título del recuadro del bono o de la fila donde hacés clic. No usa clases de Matriz, porque cambian.
- La TIR a otro precio se estima con la duration (ΔTIR ≈ −ΔP/P / MD), sin convexidad.

## Instalar para probar
1. `chrome://extensions` → activar «Modo de desarrollador» → «Cargar descomprimida» → elegir esta carpeta `extension/`.
2. Entrar a Matriz y tocar el ícono de la extensión (conviene fijarlo en la barra con el alfiler) para abrir Bonerío al costado.
3. Si el panel lateral pide ingresar, usar mail y contraseña o el link por mail: Google no deja ingresar adentro de otra página.
