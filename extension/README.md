# Bonerío Inside (prototipo)

Los botones *Ficha*, *Curva* y *Más…* del panel flotante abren una ventana con solapas (Ficha, Curva del grupo del bono, Volumen, Acciones → Pares, Brecha y canje, Futuros, Sintéticos, Pases CI vs 24 hs y Expectativas). La página se carga una sola vez (empieza al acercar el mouse al panel) y después cambia de sección por mensaje, sin recargar. Cada una muestra su sección sola en una ventana adentro de Matriz (se mueve desde el encabezado y se agranda desde la esquina), con el modo `?emb=sec` del Dashboard. El bono se elige haciendo clic en Matriz o escribiéndolo en el buscador del panel.

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

**Volumen:** «Dónde estuvo» y «Operado hoy» (la tarjeta de Resumen, período diario).

**Compacto:** la Ficha muestra encabezado, rendimiento y curva, calculadora y sensibilidad; Acciones (pares) muestra las acciones, el período, las bandas y el gráfico.
