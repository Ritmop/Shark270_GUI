import tkinter as tk
from pymodbus.client import ModbusTcpClient
import struct



#  ---------------------------------------------------------------------------------------------------------------------------------
#                                                  Funciones de comunicación con el medidor
#  ---------------------------------------------------------------------------------------------------------------------------------

def reg2var(registers,data_type):
    if(data_type == "TSTAMP"):
        tstamp_mask = 0x7f0f1f1f3f3f  
        tstamp_bytes = struct.pack('>Q',(registers[0] << 32 | registers[1] << 16 | registers[2]))
        tstamp = struct.unpack('>Q',tstamp_bytes)[0] & tstamp_mask
        tstamp_str = f"{tstamp:012X}"
        
        year = int(tstamp_str[0:2],16)
        month = int(tstamp_str[2:4],16)
        day = int(tstamp_str[4:6],16)
        hour = int(tstamp_str[6:8],16)
        minute = int(tstamp_str[8:10],16)
        second = int(tstamp_str[10:12],16)
        
        return f"{day}/{month}/{year} {hour}:{minute}:{second}"
    
    elif(data_type == "UINT32"):
        packed_bytes = struct.pack('>I', (registers[0] << 16 | registers[1]))
        return struct.unpack('>I',packed_bytes)[0]
    
    elif(data_type == "SINT32"):
        packed_bytes = struct.pack('>I', (registers[0] << 16 | registers[1]))
        return struct.unpack('>i',packed_bytes)[0]

    elif(data_type == "UINT16"):
        packed_bytes = struct.pack('>H', registers)
        return struct.unpack('>H',packed_bytes)[0]

    elif(data_type == "SINT16"):
        packed_bytes = struct.pack('>H', registers)
        return struct.unpack('>h',packed_bytes)[0]

    elif(data_type == "FLOAT"):
        packed_bytes = struct.pack('<I', (registers[0] << 16 | registers[1]))
        return struct.unpack('<f',packed_bytes)[0]

    elif(data_type == "ASCII"):
        string = ""
        for reg in registers:
            packed_bytes = struct.pack('>H', reg)
            high,low = struct.unpack('>cc',packed_bytes)
            string += high.decode('latin1') + low.decode('latin1')
        return string
    




# concect_shark270
# Esta función establece la conección con el medidor Shark270, utilizando el protocolo Modbus TCP.
# Se define la dirección IP del medidor, el número de servidor y se obtienen algunos parámetros
# del medidor como número de serie y modelo.
def connect_shark270(server_address,host_ip,port):
    try:
        # Iniciar cliente
        global slave_address
        slave_address = server_address
        global ip
        ip = host_ip
        global client
        client = ModbusTcpClient(host=ip,port=port)
        client.connect()

        # Secuencia de acceso
        try:
            # Obtener identificaciones del medidor
            # Nombre: 0,8   Numero de serie: 8,16 
            id_request = client.read_holding_registers(0,16,slave_address).registers
            type_request = client.read_holding_registers(26,4,slave_address).registers
        except:
            status_lbl.config(text="\nNo se pudo acceder al medidor.")
            connect_wndw.withdraw()
        
        # Interpretación de los datos recibidos
        meter_name = reg2var(id_request[0:9],"ASCII")
        meter_SN   = reg2var(id_request[9:17],"ASCII")
        meter_type = reg2var(type_request,"ASCII")
        status_lbl.config(text=f"\n***** Conectado *****\n IP:\t{host_ip}:{port}\n Model:\t{meter_type}\n SN:\t{meter_SN}\n Name:\t{meter_name}")
        connect_btn.config(state="disabled")
        dis_cnct_btn.config(state="active")
        polling_btn.config(state="active")
        ret_log_btn.config(state="active")
        connect_wndw.withdraw()     

    except Exception as e:
        status_lbl.config(text="\nConexión fallida {e}")
        connect_wndw.withdraw()
        
def disconnect_shark270():
    connect_btn.configure(state="active")
    polling_btn.config(state="disabled")
    status_lbl.config(text="\n***** Desconectado *****")
    client.close()

def leer_shark270(start_address, address_count, format):
    try:
        # Verificar que el medidor esté disponible para una lectura
        read_lock_status = client.read_holding_registers(9994,1,slave_address).registers[0]

        # Si está disponible, bloquear el sistema de logs para evitar interferencias con otro software
        if (read_lock_status == 0):
            client.write_register(9994,10,slave_address)
        else:
            raise

    except:
        status_lbl.config(text=f"\nEl medidor se encuentra ocupado, intente de nuevo.")
        polling_wndw.withdraw()

    try:
        # Obtener los registros solicitados.
        true_value = ""
        data_request = client.read_holding_registers(start_address-1,address_count,slave_address).registers
        data_str = f"\n#Reg\tData [Hex]\t{format}"        

        # Interpretación de los datos recibidos
        for i in range(len(data_request)):
            bytes_value = struct.pack('>H',data_request[i]).hex().upper()
            if(format == "TSTAMP" and i%3 == 0):
                if (i+2 < len(data_request)): true_value = reg2var(data_request[i:i+3],format)
                else: true_value = "Incomplete data"
            
            elif (format == "UINT32" and i%2 == 0):
                if (i+1 < len(data_request)): true_value = reg2var(data_request[i:i+2],format)
                else: true_value = "Incomplete data"

            elif (format == "SINT32" and i%2 == 0):
                if (i+1 < len(data_request)): true_value = reg2var(data_request[i:i+2],format)
                else: true_value = "Incomplete data"

            elif (format == "UINT16"):
                    true_value = reg2var(data_request[i],format)

            elif (format == "SINT16"):
                    true_value = reg2var(data_request[i],format) 

            elif (format == "FLOAT" and i%2 == 0):
                if (i+1 < len(data_request)): true_value = reg2var(data_request[i:i+2],format)
                else: true_value = "Incomplete data"

            elif (format == "ASCII" and i == 0):
                ascii_str = reg2var(data_request,format)
                true_value = ascii_str

            else:
                true_value = "   ↑" # Indicador que el registro actual es parte de un registro previo 
            
            data_str += f"\n{start_address+i}\t{bytes_value}\t\t{true_value}"  
        return_data_lbl.config(text=data_str)

        # Desbloquear el sistema de logs
        client.write_register(9994,10,slave_address)

    except Exception as e:
        status_lbl.config(text=f"Error durante lectura. {e}")
        polling_wndw.withdraw()

def retlog_shark270():
    status_lbl.config(text=f"Retrieving...")


#  ---------------------------------------------------------------------------------------------------------------------------------
#                                                          Ventanas de la GUI
#  ---------------------------------------------------------------------------------------------------------------------------------

# -----------------------------------     Ventana Connect     -----------------------------------
connect_wndw = tk.Tk()
connect_wndw.title("Connect")
connect_wndw.withdraw()

connect_lbl = tk.Label(connect_wndw, text="Network connect")
connect_lbl.grid(row=0,column=0,columnspan=2,sticky="snew")

dev_address_lbl = tk.Label(connect_wndw, text="Device Address")
dev_address_lbl.grid(row=1,column=0,sticky="w")

host_lbl = tk.Label(connect_wndw, text="Host")
host_lbl.grid(row=2,column=0,sticky="w")

port_lbl = tk.Label(connect_wndw, text="Network Port")
port_lbl.grid(row=3,column=0,sticky="w")

protocol_lbl = tk.Label(connect_wndw, text="Protocol")
protocol_lbl.grid(row=4,column=0,sticky="w")

dev_address_txt = tk.Entry(connect_wndw)
dev_address_txt.insert(0,"1")
dev_address_txt.grid(row=1,column=1,sticky="w")

host_txt = tk.Entry(connect_wndw)
host_txt.insert(0,"192.168.0.90")
host_txt.grid(row=2,column=1,sticky="w")

port_txt = tk.Entry(connect_wndw)
port_txt.insert(0,"502")
port_txt.grid(row=3,column=1,sticky="w")
port_txt.config(state="readonly")

protocol_txt = tk.Entry(connect_wndw)
protocol_txt.insert(0,"Modbus TCP")
protocol_txt.grid(row=4,column=1,sticky="w")
protocol_txt.config(state="readonly")

try_cnction_btn = tk.Button(connect_wndw, text="Connect",command=lambda: connect_shark270(int(dev_address_txt.get()),host_txt.get(),int(port_txt.get())))
try_cnction_btn.grid(row=5, column=0)

cancel_cnction_btn = tk.Button(connect_wndw, text="Cancel",command=connect_wndw.withdraw)
cancel_cnction_btn.grid(row=5, column=1)


# -----------------------------------     Ventana Polling     -----------------------------------
polling_wndw = tk.Tk()
polling_wndw.title("Polling")
polling_wndw.withdraw()

data_lbl = tk.Label(polling_wndw, text="Data polling")
data_lbl.grid(row=0,column=0,columnspan=2,sticky="snew")

start_reg_lbl = tk.Label(polling_wndw, text="Start Register")
start_reg_lbl.grid(row=1,column=0,sticky="w")

reg_count_lbl = tk.Label(polling_wndw, text="Registers Count")
reg_count_lbl.grid(row=2,column=0,sticky="w")

data_type_lbl = tk.Label(polling_wndw, text="Data format")
data_type_lbl.grid(row=3,column=0,sticky="w")

start_reg_txt = tk.Entry(polling_wndw)
start_reg_txt.insert(0,"9")
start_reg_txt.grid(row=1,column=1)

reg_count_txt = tk.Entry(polling_wndw)
reg_count_txt.grid(row=2,column=1)
reg_count_txt.insert(0,"8")

data_type_selection = tk.StringVar(polling_wndw)
data_type_selection.set("ASCII")
data_type_list = tk.OptionMenu(polling_wndw,data_type_selection,*["TSTAMP","UINT32","SINT32","UINT16","SINT16","FLOAT","ASCII"])
data_type_list.grid(row=3,column=1,sticky="w")

read_btn = tk.Button(polling_wndw, text="Request Data",command=lambda: leer_shark270(int(start_reg_txt.get()),int(reg_count_txt.get()),data_type_selection.get()))
read_btn.grid(row=4,column=0)

cancel_poll_btn = tk.Button(polling_wndw, text="Cancel", command=polling_wndw.withdraw)
cancel_poll_btn.grid(row=4,column=1)

return_data_lbl = tk.Label(polling_wndw,text="\nData output",justify="left")
return_data_lbl.grid(row=5,columnspan=2,sticky="w")

# -----------------------------------     Ventana ret logs     -----------------------------------
ret_log_wndw = tk.Tk()
ret_log_wndw.title("Retrieve Log")
ret_log_wndw.withdraw()

read_btn = tk.Button(ret_log_wndw, text="Retrieve",command=lambda: retlog_shark270())
read_btn.grid(row=4,column=0)

cancel_retlog_btn = tk.Button(ret_log_wndw, text="Cancel", command=ret_log_wndw.withdraw)
cancel_retlog_btn.grid(row=4,column=1)


# -----------------------------------     Ventana principal (Cinta de opciones)     -----------------------------------
main_wndw = tk.Tk()
main_wndw.title("Shark® 270 | MODBUS")

status_lbl = tk.Label(main_wndw,text="\nStatus...",justify="left")
status_lbl.grid(row=1,column=0,columnspan=10,sticky="w")

'''profile_btn = tk.Button(main_wndw, text="Profile")
profile_btn.grid(row=0, column=0)
conn_mgr_btn = tk.Button(main_wndw, text="Conn Mgr")
conn_mgr_btn.grid(row=0, column=3)
meter_mgr_btn = tk.Button(main_wndw, text="Meter Mgr")
meter_mgr_btn.grid(row=0, column=4)'''
ret_log_btn = tk.Button(main_wndw, text="Ret Log",state="disabled", command=ret_log_wndw.deiconify)
ret_log_btn.grid(row=0, column=1)
open_log_btn = tk.Button(main_wndw, text="Open Log")
open_log_btn.grid(row=0, column=2)
connect_btn = tk.Button(main_wndw, text="Connect", command=connect_wndw.deiconify)
connect_btn.grid(row=0, column=5)
dis_cnct_btn = tk.Button(main_wndw, text="Dis-cnct",state="disabled", command=lambda: disconnect_shark270())
dis_cnct_btn.grid(row=0, column=6)
polling_btn = tk.Button(main_wndw, text="Polling", state="disabled", command=polling_wndw.deiconify)
polling_btn.grid(row=0, column=7)
'''energy_btn = tk.Button(main_wndw, text="Energy")
energy_btn.grid(row=0, column=8)
hermonic_btn = tk.Button(main_wndw, text="Harmonic")
hermonic_btn.grid(row=0, column=9)
phasor_btn = tk.Button(main_wndw, text="Phasor")
phasor_btn.grid(row=0, column=10)
flicker_btn = tk.Button(main_wndw, text="Flicker")
flicker_btn.grid(row=0, column=11)
log_stats_btn = tk.Button(main_wndw, text="Log Stats")
log_stats_btn.grid(row=0, column=12)
dev_stats_btn = tk.Button(main_wndw, text="Dev Stats")
dev_stats_btn.grid(row=0, column=13)
alarms_btn = tk.Button(main_wndw, text="Alarms")
alarms_btn.grid(row=0, column=14)'''

# Ejecutar la aplicación
main_wndw.mainloop()


