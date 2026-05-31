from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import urllib.parse  # MODIFICADO: Agregado para codificar los mensajes de WhatsApp

app = Flask(__name__)
app.secret_key = 'Ari0207#'  # Clave de cifrado para las sesiones de usuario

# ==========================================
# CONFIGURACIÓN DE LA BASE DE DATOS FIXED
# ==========================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'boutique.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# MODELOS DE LA BASE DE DATOS
# ==========================================

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_alias_original = db.Column('nombre', db.String(150), nullable=False) # Mapeo nativo
    cedula = db.Column(db.String(50), nullable=False, unique=True)
    telefono = db.Column(db.String(50))
    direccion = db.Column(db.String(300))
    deuda_total = db.Column(db.Float, default=0.0)
    movimientos = db.relationship('Movimiento', backref='cliente', lazy=True, cascade="all, delete-orphan")

    # Mantenemos la propiedad .nombre para compatibilidad con el resto de tus rutas
    @property
    def nombre(self):
        return self.name_alias_original
    @nombre.setter
    def nombre(self, valor):
        self.name_alias_original = valor

class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # 'VENTA' o 'ABONO'
    detalles = db.Column(db.Text, nullable=False)
    monto_total = db.Column(db.Float, default=0.0)
    abono_inicial = db.Column(db.Float, default=0.0)
    monto_movimiento = db.Column(db.Float, default=0.0)
    resta = db.Column(db.Float, default=0.0)
    fecha = db.Column(db.String(50), nullable=False)

# MODELO INVENTARIO ADAPTADO CON CAMPOS DE CONTROL DE PROVEEDORES Y FECHAS
class Inventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_factura = db.Column(db.String(50), nullable=False)
    proveedor = db.Column(db.String(150), nullable=False, default="VARIOS")
    fecha_factura = db.Column(db.String(50), nullable=False)
    # Campos de Cuentas por Pagar del Proveedor
    monto_factura = db.Column(db.Float, default=0.0)
    abono_proveedor = db.Column(db.Float, default=0.0)
    resta_proveedor = db.Column(db.Float, default=0.0)
    # Características del Producto
    prenda = db.Column(db.String(150), nullable=False)
    cantidad_inicial = db.Column(db.Integer, default=0)
    cantidad_actual = db.Column(db.Integer, default=0)
    precio_costo = db.Column(db.Float, default=0.0)
    precio_venta = db.Column(db.Float, default=0.0)

# NUEVO MODELO DE CONTROL: HISTORIAL DE PAGOS A PROVEEDORES
class HistorialAbonoProveedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote_factura = db.Column(db.String(50), nullable=False)
    monto_abonado = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.String(50), nullable=False)

# Creación automática de tablas en el arranque limpio
with app.app_context():
    db.create_all()

# ==========================================
# CONTROLADORES: LOGIN Y CLIENTES
# ==========================================

@app.route('/')
def login():
    if session.get('autenticado'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/autenticar', methods=['POST'])
def autenticar():
    clave = request.form.get('clave')
    destino = request.form.get('destino')
    
    if clave == "Ari0207#":
        session['autenticado'] = True
        if destino == "inventario":
            return redirect(url_for('inventario'))
        return redirect(url_for('dashboard'))
    else:
        return "<script>alert('Contraseña Incorrecta'); window.location='/';</script>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    clientes = Cliente.query.order_by(Cliente.name_alias_original).all()
    
    # MODIFICADO: Generar dinámicamente los mensajes y enlaces de WhatsApp LIMPIANDO EL TELÉFONO
    for c in clientes:
        deuda = float(c.deuda_total or 0.0)
        nombre_cliente = c.nombre
        telefono_crudo = str(c.telefono or '').strip()
        
        # --- FILTRO DE LIMPIEZA INTELIGENTE PARA EL TELÉFONO ---
        # 1. Deja únicamente los dígitos (elimina guiones, espacios, letras)
        tel_limpio = "".join(filter(str.isdigit, telefono_crudo))
        
        # 2. Si empieza por '0' (ej. 0424...), se le remueve el cero inicial
        if tel_limpio.startswith("0"):
            tel_limpio = tel_limpio[1:]
            
        # 3. Si no tiene el código de área internacional de Venezuela (58), se le coloca adelante
        if tel_limpio and not tel_limpio.startswith("58"):
            tel_final = "58" + tel_limpio
        else:
            tel_final = tel_limpio
        
        # 🟢 CASO 1: Cliente SOLVENTE
        if deuda == 0.0:
            texto_msg = f"Estimado(a) {nombre_cliente}, la Boutique Moda Fashions de la Lic. Alejandra Contreras le informa que su estado de cuenta se encuentra SOLVENTE. ¡Gracias por su preferencia!"
        
        # 🔴 CASO 2: Cliente DEUDOR (Deuda mayor o igual a $20.00)
        elif deuda >= 20.00:
            texto_msg = f"Boutique Moda Fashions de la Lic. Alejandra Contreras le recuerda que presenta un estado DEUDOR con un saldo pendiente de ${deuda:.2f}. Le agradecemos realizar un abono a la brevedad para regularizar su cuenta. ¡Muchas gracias!"
        
        # 🟡 CASO 3: Cliente PENDIENTE (Deuda menor a $20.00)
        else:
            texto_msg = f"Estimado(a) {nombre_cliente}, la Boutique Moda Fashions de la Lic. Alejandra Contreras le recuerda que presenta un saldo pendiente de ${deuda:.2f}. Le invitamos a realizar un abono a su cuenta. ¡Feliz día!"
        
        # Inyectamos el link codificado con el teléfono formateado sin ceros molestos
        texto_codificado = urllib.parse.quote(texto_msg)
        
        if tel_final:
            c.whatsapp_link = f"https://api.whatsapp.com/send?phone={tel_final}&text={texto_codificado}"
        else:
            c.whatsapp_link = "#"
        
    return render_template('dashboard.html', clientes=clientes)

@app.route('/registrar', methods=['POST'])
def registrar():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    tipo_operacion = request.form.get('tipo_operacion')
    nombre = request.form.get('nombre').upper().strip()
    cedula = request.form.get('cedula').strip()
    telefono = request.form.get('telefono').strip()
    direccion = request.form.get('direccion').upper().strip()
    fecha_actual = datetime.now().strftime("%d/%m/%Y %I:%M %p")

    cliente = Cliente.query.filter_by(cedula=cedula).first()
    
    if cliente:
        if cliente.nombre.upper().strip() != nombre:
            return f"<script>alert('ERROR: La cédula {cedula} ya se encuentra registrada a nombre de {cliente.nombre}. Verifique los datos.'); window.location='/dashboard';</script>"
    else:
        cliente = Cliente(nombre=nombre, cedula=cedula, telefono=telefono, direccion=direccion, deuda_total=0.0)
        db.session.add(cliente)
        db.session.commit()

    if tipo_operacion == "VENTA":
        prendas = request.form.getlist('prenda[]')
        cantidades = request.form.getlist('cant[]')
        monto_total = float(request.form.get('monto_total') or 0.0)
        abono_inicial = float(request.form.get('abono_inicial') or 0.0)
        
        detalles_lista = []
        for i in range(len(prendas)):
            if prendas[i].strip():
                nombre_limpio = prendas[i].split(" ($")[0].upper().strip()
                inv_item = Inventario.query.filter_by(prenda=nombre_limpio).first()
                cant_vender = int(cantidades[i] or 1)
                
                if inv_item:
                    inv_item.cantidad_actual -= cant_vender
                    if inv_item.cantidad_actual < 0:
                        inv_item.cantidad_actual = 0
                
                detalles_lista.append(f"{cant_vender}x {nombre_limpio}")
                
        detalles_texto = ", ".join(detalles_lista) if detalles_lista else "COMPRA DE MERCANCÍA"

        saldo_restante = monto_total - abono_inicial
        cliente.deuda_total += saldo_restante

        mov = Movimiento(
            cliente_id=cliente.id,
            tipo="VENTA",
            detalles=detalles_texto,
            monto_total=monto_total,
            abono_inicial=abono_inicial,
            monto_movimiento=0.0,
            resta=cliente.deuda_total,
            fecha=fecha_actual
        )
        db.session.add(mov)

    elif tipo_operacion == "ABONO":
        monto_abono = float(request.form.get('abono') or 0.0)
        cliente.deuda_total -= monto_abono
        if cliente.deuda_total < 0: 
            cliente.deuda_total = 0.0

        mov = Movimiento(
            cliente_id=cliente.id,
            tipo="ABONO",
            detalles="ABONO RECIBIDO EN CAJA",
            monto_total=0.0,
            abono_inicial=0.0,
            monto_movimiento=monto_abono,
            resta=cliente.deuda_total,
            fecha=fecha_actual
        )
        db.session.add(mov)

    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/editar_cliente', methods=['POST'])
def editar_cliente():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    cedula = request.form.get('cedula').strip()
    cliente = Cliente.query.filter_by(cedula=cedula).first()
    if cliente:
        cliente.nombre = request.form.get('nombre').upper().strip()
        cliente.telefono = request.form.get('telefono').strip()
        cliente.direccion = request.form.get('direccion').upper().strip()
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/historial/<int:cliente_id>')
def historial(cliente_id):
    if not session.get('autenticado'):
        return jsonify([])
    movs = Movimiento.query.filter_by(cliente_id=cliente_id).order_by(Movimiento.id.desc()).all()
    resultado = []
    for m in movs:
        resultado.append({
            'fecha': m.fecha, 'tipo': m.tipo, 'detalles': m.detalles,
            'monto_total': m.monto_total, 'abono_inicial': m.abono_inicial,
            'monto_movimiento': m.monto_movimiento, 'resta': m.resta
        })
    return jsonify(resultado)

@app.route('/eliminar/<int:id>')
def eliminar_cliente(id):
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    cliente = Cliente.query.get(id)
    if cliente:
        db.session.delete(cliente)
        db.session.commit()
    return redirect(url_for('dashboard'))

# ==========================================
# MÓDULO DE INVENTARIO Y CONTROL DE PROVEEDORES
# ==========================================

@app.route('/inventario')
def inventario():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    productos = Inventario.query.order_by(Inventario.id.desc()).all()
    
    inversion_total = 0.0
    ganancia_proyectada = 0.0
    ganancia_real = 0.0
    
    for p in productos:
        inversion_total += (p.cantidad_inicial * p.precio_costo)
        ganancia_proyectada += (p.cantidad_inicial * (p.precio_venta - p.precio_costo))
        
        cant_vendida = p.cantidad_inicial - p.cantidad_actual
        if cant_vendida > 0:
            ganancia_real += (cant_vendida * (p.precio_venta - p.precio_costo))
            
    return render_template('inventario.html', 
                           productos=productos, 
                           inversion=inversion_total, 
                           proyectada=ganancia_proyectada, 
                           real=ganancia_real)

@app.route('/inventario/guardar', methods=['POST'])
def guardar_inventario():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    
    id_producto = request.form.get('id_producto')
    lote = request.form.get('lote_factura').upper().strip()
    proveedor = request.form.get('proveedor').upper().strip()
    
    fecha_raw = request.form.get('fecha_factura')
    if fecha_raw:
        try:
            fecha_dt = datetime.strptime(fecha_raw, "%Y-%m-%d")
            fecha_factura = fecha_dt.strftime("%d/%m/%Y")
        except:
            fecha_factura = fecha_raw
    else:
        fecha_factura = datetime.now().strftime("%d/%m/%Y")
        
    m_factura = float(request.form.get('monto_factura') or 0.0)
    m_abono = float(request.form.get('abono_proveedor') or 0.0)
    m_resta = m_factura - m_abono
    
    prendas = request.form.getlist('prenda[]')
    cantidades = request.form.getlist('cantidad[]')
    costos = request.form.getlist('precio_costo[]')
    ventas = request.form.getlist('precio_venta[]')
    
    if id_producto:  
        prod = Inventario.query.get(id_producto)
        if prod:
            viejos_items = Inventario.query.filter_by(lote_factura=prod.lote_factura).all()
            for item in viejos_items:
                item.lote_factura = lote
                item.proveedor = proveedor
                item.fecha_factura = fecha_factura
                item.monto_factura = m_factura
                item.abono_proveedor = m_abono
                item.resta_proveedor = m_resta
            
            prod.prenda = prendas[0].upper().strip()
            prod.cantidad_actual = int(cantidades[0] or 0)
            if prod.cantidad_actual > prod.cantidad_inicial:
                prod.cantidad_inicial = prod.cantidad_actual
            prod.precio_costo = float(costos[0] or 0.0)
            prod.precio_venta = float(ventas[0] or 0.0)
    else:  
        for i in range(len(prendas)):
            if prendas[i].strip():
                nombre_prenda = prendas[i].upper().strip()
                cant = int(cantidades[i] or 0)
                p_costo = float(costos[i] or 0.0)
                p_venta = float(ventas[i] or 0.0)
                
                nuevo_item = Inventario(
                    lote_factura=lote,
                    proveedor=proveedor,
                    fecha_factura=fecha_factura,
                    monto_factura=m_factura,
                    abono_proveedor=m_abono,
                    resta_proveedor=m_resta,
                    prenda=nombre_prenda,
                    cantidad_inicial=cant,
                    cantidad_actual=cant,
                    precio_costo=p_costo,
                    precio_venta=p_venta
                )
                db.session.add(nuevo_item)
        
        if m_abono > 0:
            historial_inicial = HistorialAbonoProveedor(
                lote_factura=lote,
                monto_abonado=m_abono,
                fecha_pago=datetime.now().strftime("%d/%m/%Y %I:%M %p")
            )
            db.session.add(historial_inicial)
                
    db.session.commit()
    return redirect(url_for('inventario'))

@app.route('/inventario/eliminar/<int:id>')
def eliminar_inventario(id):
    if not session.get('autenticado'):
        return redirect(url_for('login'))
    prod = Inventario.query.get(id)
    if prod:
        db.session.delete(prod)
        db.session.commit()
    return redirect(url_for('inventario'))

@app.route('/inventario/vender_simular/<int:id>', methods=['POST'])
def vender_simular(id):
    if not session.get('autenticado'): 
        return redirect(url_for('login'))
    prod = Inventario.query.get(id)
    if prod and prod.cantidad_actual > 0:
        prod.cantidad_actual -= 1
        db.session.commit()
    return redirect(url_for('inventario'))

# ==========================================
# RUTAS DE CONTROL API COMPLEMENTARIAS
# ==========================================

@app.route('/api/productos_venta')
def api_productos_venta():
    if not session.get('autenticado'):
        return jsonify([])
    productos = Inventario.query.filter(Inventario.cantidad_actual > 0).all()
    return jsonify([{
        'prenda': p.prenda,
        'stock': p.cantidad_actual,
        'precio': p.precio_venta
    } for p in productos])

@app.route('/api/historial_proveedor/<string:lote_factura>')
def api_historial_proveedor(lote_factura):
    if not session.get('autenticado'):
        return jsonify({'error': 'No autorizado'}), 401
        
    prod = Inventario.query.filter_by(lote_factura=lote_factura).first()
    if not prod:
        return jsonify({'error': 'Factura no encontrada'}), 404
        
    abonos = HistorialAbonoProveedor.query.filter_by(lote_factura=lote_factura).all()
    historial_lista = [{'monto': a.monto_abonado, 'fecha': a.fecha_pago} for a in abonos]
    
    return jsonify({
        'lote_factura': prod.lote_factura,
        'proveedor': prod.proveedor,
        'monto_total': prod.monto_factura,
        'abono_realizado': prod.abono_proveedor,
        'resta_pendiente': prod.resta_proveedor,
        'historial': historial_lista
    })

@app.route('/inventario/abonar', methods=['POST'])
def registrar_abono_posterior():
    if not session.get('autenticado'):
        return redirect(url_for('login'))
        
    lote_factura = request.form.get('modal_lote')
    monto_abono = float(request.form.get('monto_nuevo_abono') or 0.0)
    
    if monto_abono <= 0:
        return redirect(url_for('inventario'))
        
    items = Inventario.query.filter_by(lote_factura=lote_factura).all()
    if items:
        for item in items:
            item.abono_proveedor += monto_abono
            item.resta_proveedor = item.monto_factura - item.abono_proveedor
            if item.resta_proveedor < 0:
                item.resta_proveedor = 0.0
                
        nuevo_pago = HistorialAbonoProveedor(
            lote_factura=lote_factura,
            monto_abonado=monto_abono,
            fecha_pago=datetime.now().strftime("%d/%m/%Y %I:%M %p")
        )
        db.session.add(nuevo_pago)
        db.session.commit()
        
    return redirect(url_for('inventario'))

if __name__ == '__main__':
    app.run(debug=True)
