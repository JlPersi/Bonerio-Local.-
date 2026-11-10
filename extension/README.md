# Bonerío Inside (prototipo)

Los botones *Curva* y *Más…* del panel flotante abren una ventana con cuatro solapas: Curva, Brecha y canje, Pases y Expectativas (inflación y devaluación implícitas, y las forwards de tasa fija, CER, TAMAR y dollar linked). La página se carga una sola vez (empieza al acercar el mouse al panel) y después cambia de sección por mensaje, sin recargar. Cada una muestra su sección sola en una ventana adentro de Matriz (se mueve desde el encabezado y se agranda desde la esquina), con el modo `?emb=sec` del Dashboard. El bono se elige haciendo clic en Matriz o escribiéndolo en el buscador del panel.

Extensión de Chrome que muestra, al lado de Matriz, los datos de Bonerío Local para el bono que tenés abierto:
TIR al cierre, TIR estimada al precio de la pantalla o de la boleta, duration, días al vencimiento y un semáforo contra la curva
(TIR = a + b·ln(días) dentro del grupo, con la misma ley si alcanza; ±25 pb = en línea).

- El precio sale de la pantalla del usuario (boleta, «Cierre» o «Cierre Ant.» del recuadro del bono). Bonerío solo pone `data/api/curvas.json`: nada en vivo de Primary.
- El ticker se toma de la boleta, del título del recuadro del bono o de la fila donde hacés clic. No usa clases de Matriz, porque cambian.
- La TIR a otro precio se estima con la duration (ΔTIR ≈ −ΔP/P / MD), sin convexidad.

**Datos adentro de los recuadros de Matriz:** debajo de «Pos / P&L» de cada recuadro con libro se agregan filas con el mismo estilo (TIR, DM, contra la curva, días…). Con ⚙ en el panel se eligen cuáles o se apagan. En los bonos en dólares la TIR usa el precio solo en el recuadro de la especie D (MEP), que es el que toma Bonerío.

**Más instrumentos:** futuros de dólar (DLR/NOV26: TNA implícita y devaluación mensual contra el A3500) y acciones del panel (precio, rendimientos, beta, P/E, P/VL y EV/EBITDA).

**A la boleta:** «→ Boleta» o un clic en un punto de un gráfico o en una fila de una tabla de la ventana escribe el ticker en «Instrumento» de Matriz y elige la sugerencia de 24 hs, en la moneda elegida en ⚙ (pesos, MEP «D» o CCL «C») para los bonos en dólares. Después completa «Precio» con el último (o el cierre anterior) del recuadro de ese ticker en Matriz o, si no hay recuadro, con el «Últ» del Mini-Panel de precios (y, si tampoco está, con el cierre de Bonerío, avisando en el panel) y «Cantidad» con la cantidad por defecto (⚙). No aprieta Comprar ni Vender: eso lo hace el usuario.

## Instalar para probar
1. `chrome://extensions` → activar «Modo de desarrollador» → «Cargar descomprimida» → elegir esta carpeta `extension/`.
2. Entrar a Matriz: el panel aparece solo. El ícono de la extensión lo muestra u oculta.
3. Si el panel lateral pide ingresar, usar mail y contraseña o el link por mail: Google no deja ingresar adentro de otra página.

**Curva:** un desplegable arriba del gráfico elige cualquier curva (Soberanos USD, Lecaps, CER, TAMAR, Dollar linked, Duales, ONs, Provinciales, Futuros) sin tocar Matriz.

**Fichas fijas:** 📌 en el panel abre una ficha chica del bono activo, con sus propios nominales para la boleta. Podés abrir todas las que quieras y moverlas; quedan guardadas para la próxima vez. Se actualizan con el precio de la pantalla.

**Ventana:** abre con el tamaño justo de cada sección. Si la agrandás o achicás desde la esquina, el contenido se acomoda a ese tamaño; doble clic en el encabezado vuelve al tamaño justo. 🔓/🔒 la fija (no se mueve ni cambia de tamaño). Recuerda dónde la dejaste.


**Datos:** el botón *Datos ▾* del panel y de cada ficha fija despliega todos los datos de la ficha del bono (TIR, duraciones, convexidad, valor técnico, intereses corridos, paridad, cupón) y una calculadora de precio ↔ TIR con nominales. Son datos de cierre de Bonerío.

**Colores:** panel, fichas y ventana usan el estilo oscuro de Bonerío Local (negro y dorado) para no confundirse con Matriz.

**Plazo máximo:** en las curvas en pesos, un segundo desplegable elige hasta qué plazo se ven los bonos (por defecto, todos: DICP, PARP, CUAP…).

**Ventana nítida:** la sección no se escala; se acomoda al ancho de la ventana y lo que sobra se desplaza. Los desplegables salen en su lugar y no se cortan. Con tamaño a mano, en las curvas el gráfico llena la ventana.

**Sensibilidad:** en Datos, la tabla de cuánto cambia el precio (y tu resultado con los nominales) si la TIR se mueve ±25 a ±200 pb.

**Pase CI ↔ 24 hs:** en el panel, *Colocar* (comprás en CI y vendés en 24 hs) o *Tomar* (al revés). Carga la primera pata en la boleta con el precio del recuadro de ese plazo; apretás Comprar o Vender y después *Pata 2* carga la otra.

**Acceso:** abierta para todos hasta el viernes 13/11. Desde el 14/11, solo cuentas con Bonerío PRO o en sus 7 días de prueba (lo dice la página de Bonerío con la sesión de la cuenta). Sin sesión, el panel pide entrar.

**Descarga para usuarios:** https://boneriolocal.com.ar/inside.html (el .zip está en `descargas/`).


**Pases por pata (0.18.1):** la solapa Pases muestra el monitor y la tabla de especies. Cada fila tiene botones *Comprar CI / Vender 24 hs* y *Vender CI / Comprar 24 hs*: cada uno carga esa pata en la boleta (CI o 24 hs) con el precio del recuadro de ese plazo y los nominales en cartera si están cargados (`CIMX.nom`).

**Filtros en ONs y provinciales:** tipo, gráfico, liquidez, eje X, empresa/provincia, sector y buscar, compactos arriba del gráfico.

**Sensibilidad al costado:** se abre en un cuadro al lado del panel o de la ficha (a la derecha si entra) y lo sigue si lo movés.

**Alerta de pases (0.18.2):** con la rueda abierta, la página (escondida) vigila tus especies en cartera de Pases cada 10 s. Si colocar o tomar le gana a la caución por más de tu umbral, suena un «check» y aparece arriba un aviso con las dos patas (Comprar/Vender CI y 24 hs), que cargan la boleta con tus nominales. Cada pase avisa una vez cada 30 minutos. Se apaga en ⚙.

**Precios de tu Matriz (1.0.1):** cada 2 s la extensión lee los precios que muestra tu Matriz (último y mejores puntas de cada recuadro con libro, en CI o 24 hs, y el «Últ» del Mini-Panel) y los manda a la ventana (`bnrPx`). La página los pone por encima de los suyos (stream y data912, solo si el precio es parecido) y redibuja: curvas, TIR, pases y alertas se calculan con lo que ves, en tiempo real. En las patas del pase la boleta toma la punta: comprás a la venta, vendés a la compra (si no se lee el libro, el último).
