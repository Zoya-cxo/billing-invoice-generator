import graphviz

g = graphviz.Graph('ER', engine='neato')
g.attr(overlap='false', splines='true', sep='+15', bgcolor='#eaf1f8')
g.attr('graph', fontname='Helvetica')

ENTITY_FILL = '#3dc9c0'
REL_FILL = '#183d6e'
ATTR_FILL = '#6fa8dc'
EDGE_COLOR = '#7a92a3'

def entity(name, label, pos):
    g.node(name, label=label, shape='box', style='filled,rounded',
           fillcolor=ENTITY_FILL, fontname='Helvetica-Bold', fontcolor='black',
           color='#2a9d94', penwidth='2', pos=pos, pin='true', fontsize='14')

def relationship(name, label, pos):
    g.node(name, label=label, shape='diamond', style='filled',
           fillcolor=REL_FILL, fontcolor='white', fontname='Helvetica-Bold',
           pos=pos, pin='true', fontsize='12', width='1.3', height='0.8')

def attribute(name, label, pos, derived=False, key=False):
    disp = f'<<U>{label}</U>>' if key else label
    style = 'filled,dashed' if derived else 'filled'
    g.node(name, label=disp, shape='ellipse', style=style,
           fillcolor=ATTR_FILL, fontname='Helvetica', pos=pos, pin='true', fontsize='11')

def attach(entity_name, attr_name):
    g.edge(entity_name, attr_name, color=EDGE_COLOR, len='1.0')

def link(a, b, card_a, card_b):
    g.edge(a, b, color=EDGE_COLOR, penwidth='1.4',
            headlabel=card_b, taillabel=card_a,
            labeldistance='2.2', fontsize='12', fontname='Helvetica-Bold')

entity('CUSTOMER', 'Customer', pos='0,0!')
entity('INVOICE', 'Invoice', pos='6,0!')
entity('INVOICEITEM', 'InvoiceItem', pos='12,0!')
entity('PRODUCT', 'Product', pos='18,2.5!')
entity('PAYMENT', 'Payment', pos='6,-6!')
entity('COMPANY', 'Company', pos='9,7.5!')

relationship('PLACES', 'Places', pos='3,0!')
relationship('CONTAINS', 'Contains', pos='9,0!')
relationship('REFERENCED_BY', 'Referenced\nBy', pos='15,1.5!')
relationship('RECEIVES', 'Receives', pos='6,-3!')

link('CUSTOMER', 'PLACES', '1', '')
link('PLACES', 'INVOICE', '', 'N')
link('INVOICE', 'CONTAINS', '1', '')
link('CONTAINS', 'INVOICEITEM', '', 'N')
link('PRODUCT', 'REFERENCED_BY', '1', '')
link('REFERENCED_BY', 'INVOICEITEM', '', 'N')
link('INVOICE', 'RECEIVES', '1', '')
link('RECEIVES', 'PAYMENT', '', 'N')

g.edge('COMPANY', 'INVOICE', style='dashed', color=EDGE_COLOR, penwidth='1.2',
       label='snapshot source\n(no FK)', fontsize='10', fontname='Helvetica')

attribute('cust_id', 'id', pos='-3,3!', key=True)
attribute('cust_name', 'name', pos='-1,3.5!')
attribute('cust_email', 'email', pos='1,3.8!')
attribute('cust_phone', 'phone', pos='-3.5,0.5!')
attribute('cust_gstin', 'gstin\n(nullable)', pos='-3.5,-2!')
attribute('cust_addr', 'billing_address', pos='-1,-3!')
attribute('cust_state', 'state', pos='-5,2!')
for a in ['cust_id','cust_name','cust_email','cust_phone','cust_gstin','cust_addr','cust_state']:
    attach('CUSTOMER', a)

attribute('inv_id', 'id', pos='2.5,4!', key=True)
attribute('inv_num', 'invoice_number\n(unique)', pos='4.5,4.8!')
attribute('inv_status', 'status', pos='6.5,5!')
attribute('inv_issue', 'issue_date', pos='8.5,4.6!')
attribute('inv_due', 'due_date', pos='10,3.8!')
attribute('inv_subtotal', 'subtotal', pos='3,2.5!', derived=True)
attribute('inv_taxtotal', 'tax_total', pos='9.5,2.3!', derived=True)
attribute('inv_total', 'total', pos='6.5,3.2!', derived=True)
attribute('inv_irn', 'irn (nullable)', pos='9,1.7!')
attribute('inv_qr', 'qr_code (nullable)', pos='4.5,-1.8!')
attribute('inv_seller_name', 'seller_name\n(snapshot)', pos='2.5,6!')
attribute('inv_seller_gstin', 'seller_gstin\n(snapshot)', pos='4.5,6.8!')
attribute('inv_seller_state', 'seller_state\n(snapshot)', pos='7,6.5!')
attribute('inv_seller_addr', 'seller_address\n(snapshot)', pos='0.5,5!')
for a in ['inv_id','inv_num','inv_status','inv_issue','inv_due','inv_subtotal','inv_taxtotal','inv_total','inv_irn','inv_qr','inv_seller_name','inv_seller_gstin','inv_seller_state','inv_seller_addr']:
    attach('INVOICE', a)

attribute('item_id', 'id', pos='9,-2!', key=True)
attribute('item_qty', 'quantity', pos='11,-3.5!')
attribute('item_price', 'unit_price\n(snapshot)', pos='13,-4.5!')
attribute('item_tax', 'tax_rate\n(snapshot)', pos='15,-5!')
attribute('item_disc', 'discount', pos='17,-4.5!')
attribute('item_hsn', 'hsn_sac_code\n(snapshot)', pos='15.5,-2!')
attribute('item_linetotal', 'line_total', pos='12,-6.5!', derived=True)
for a in ['item_id','item_qty','item_price','item_tax','item_disc','item_hsn','item_linetotal']:
    attach('INVOICEITEM', a)

attribute('prod_id', 'id', pos='16,5!', key=True)
attribute('prod_name', 'name', pos='19,5.5!')
attribute('prod_price', 'unit_price', pos='21,4!')
attribute('prod_tax', 'default_tax_rate', pos='21,1.5!')
attribute('prod_hsn', 'hsn_sac_code', pos='19,0!')
for a in ['prod_id','prod_name','prod_price','prod_tax','prod_hsn']:
    attach('PRODUCT', a)

for a in ['prod_id','prod_name','prod_price','prod_tax','prod_hsn']:
    attach('PRODUCT', a)

attribute('comp_id', 'id', pos='5.5,8!', key=True)
attribute('comp_name', 'name', pos='8,9!')
attribute('comp_gstin', 'gstin', pos='11,9!')
attribute('comp_state', 'state', pos='13,8!')
attribute('comp_addr', 'registered_address', pos='9,10!')
for a in ['comp_id','comp_name','comp_gstin','comp_state','comp_addr']:
    attach('COMPANY', a)

attribute('pay_id', 'id', pos='3,-7!', key=True)
attribute('pay_amount', 'amount', pos='5,-8.5!')
attribute('pay_date', 'payment_date', pos='7.5,-9!')
attribute('pay_method', 'method\n(enum: cash/upi/\nbank_transfer/cheque)', pos='9.5,-8!')
for a in ['pay_id','pay_amount','pay_date','pay_method']:
    attach('PAYMENT', a)

g.node('legend', shape='box', style='filled', fillcolor='white', color='#7a92a3',
       fontname='Helvetica', fontsize='10', pos='-2,-8!',
       label='Legend:\nUnderlined = Primary Key\nDashed ellipse = Derived attribute\nDashed edge = Conceptual link, not a live FK')

g.render('./billing_er_diagram', format='png', cleanup=True)
g.render('./billing_er_diagram', format='svg', cleanup=True)
print("done")
