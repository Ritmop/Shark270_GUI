import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from pymodbus.client import ModbusTcpClient
import struct
import pandas as pd
import os
import subprocess

#  ---------------------------------------------------------------------------------------------------------------------------------
#                                                             SHARK270 MODBUS GUI
#  ---------------------------------------------------------------------------------------------------------------------------------

# INTEK Guatemala
# Junio 2024
# Desarrollado por:
#   Judah Pérez
#   Carlos Valdez

# Este script genera una interfaz gráfica para cominucarse con medidores Shark270. La comunicación se basa en el protocolo MODBUS.
# Los objetivos principales de la aplicación son:
#   - Polling: leer registros e interpretarlos en diferentes formatos [TSTAMP,UINT32,SINT32,UINT16,SINT16,FLOAT,ASCII].
#   - Log Retrival: recuperar logs históricos 1-6.

# NOTAS:
#   - Enlace a la guía del protocolo MODBUS para el Shark 270:
#       https://www.electroind.com/products/Shark_270/pdf/manuals/Shark-270-Meter-Modbus-Protocol-Application-Guide_E159718.pdf
#   - El protocolo utilizado es MODBUS TCP.
#   - Para la recuperación de los logs se utiliza la función de auto-incremento.
#   - Al recuperar un Histórico se obtiene el log completo, tarea que puede tardar varios minutos en completarse. En ocasiones puede parecer
#       que la aplicación se ha congelado, sin embargo sigue leyendo información del medidor y la interfaz se actualizará una vez finalizada
#       la tarea.
#   - Al acoplar un log se escribe el valor 0x000B.
#   - La aplicación considera que el medidor no cuenta con seguridad, es decir no contempla un inicio de sesión antes de acceder al medidor.
#   - Utilizar los botones "Cancel" para cerrar ventanas, NO UTILIZAR LOS BOTONES [X] EN EL ENCABEZADO DE LAS VENTANAS (Genera error
#       al intentar abrir la ventana nuevamente).
#   - Los logs son exportados a la carpeta "ExportedLogs" que se crea en la misma ruta donde se encuentre este archivo de python.
#   - La aplicación utiliza el archivo "Shark270-Meter-Readings-Register-Table.xlsx" para reconocer el nombre y tamaño de los
#       registros de las mediciones del medidor. Si se obtiene un error durante la recuperación de los logs es posible que el Histórico
#       contenga una variable que no esté documentada en la tabla de Excel.
#   - El archivo "Shark270-Meter-Readings-Register-Table.xlsx" debe estar en la misma ruta que este archivo de python.


#  ---------------------------------------------------------------------------------------------------------------------------------
#                                                  Lectura de la tabla de registros MODBUS
#  ---------------------------------------------------------------------------------------------------------------------------------

# Cambiar el directorio de trabajo a donde está guardado el archivo .py
os.chdir(os.path.dirname(os.path.abspath(__file__)))
file_path = "Shark270-Meter-Readings-Register-Table.xlsx"
reg_table = pd.read_excel(file_path)

#  ---------------------------------------------------------------------------------------------------------------------------------
#                                                  Funciones de comunicación con el medidor
#  ---------------------------------------------------------------------------------------------------------------------------------

# reg2var
# Esta función permite interpretar los registros obtenidos del medidor
# según el formato en el que está almacenado.
# Parámetros:
# registers - lista de bytes para interpretar
# data_type - formato de interpretación (TSTAMP, UINT32/16, SINT32/16, FLOAT, ASCII )
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
        
        return f"{day:02}/{month:02}/20{year:02} {hour:02}:{minute:02}:{second:02}"
    
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
# Parámetros:
# server_address - número de esclavo del medidor
# ip - dirección IP del medidor
# port - puerto de conexión, 502 por defecto
def connect_shark270(server_address,ip,port):
    try:
        # Iniciar cliente
        global slave_address
        slave_address = server_address
        global client
        client = ModbusTcpClient(host=ip,port=port)
        client.connect()

        # Secuencia de acceso
        try:
            # Obtener identificaciones del medidor
            id_request = client.read_holding_registers(0,16,slave_address).registers
            type_request = client.read_holding_registers(26,4,slave_address).registers
        except Exception as e:
            status_lbl.config(text=f"\n (X) No se pudo acceder al medidor.{e}")
            connect_wndw.withdraw()
        
        # Interpretación de los datos recibidos
        meter_name = reg2var(id_request[0:8],"ASCII")
        global meter_SN
        meter_SN   = reg2var(id_request[8:16],"ASCII")
        meter_type = reg2var(type_request,"ASCII")
        status_lbl.config(text=f"\n (!) Conectado\n IP:\t{ip}:{port}\n Model:\t{meter_type}\n SN:\t{meter_SN}\n Name:\t{meter_name}")
        connect_btn.config(state="disabled")
        dis_cnct_btn.config(state="active")
        polling_btn.config(state="active")
        ret_log_btn.config(state="active")
        connect_wndw.withdraw()     

    except Exception as e:
        status_lbl.config(text="\n(X) Conexión fallida {e}")
        connect_wndw.withdraw()

# disconnect_shark270
# Esta función termina la conexión con el medidor.       
def disconnect_shark270():
    connect_btn.configure(state="active")
    polling_btn.config(state="disabled")    
    ret_log_btn.config(state="disabled")
    dis_cnct_btn.config(state="disabled")
    status_lbl.config(text="\n(!) Desconectado")
    client.close()

# leer_shark270
# Esta es la función que permite leer registros del medidor, integra la función reg2var
# para interpretar directamente los registros.
# Parámetros:
# start_adress - registro donde inicia la lectura
# address_count - cantidad de registros a leer
# format - formato para interpretar todos los datos
def leer_shark270(start_address, address_count, format):

    try:
        # Obtener los registros solicitados.
        true_value = ""
        data_request = client.read_holding_registers(start_address-1,address_count,slave_address).registers
        data_str = f"\n#Reg\tData [Hex]\t\t{format}"        

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
        return_data_lbl.config(state=tk.NORMAL)
        return_data_lbl.delete(1.0, tk.END)
        return_data_lbl.insert(tk.END,data_str)
        return_data_lbl.config(state=tk.DISABLED)

    except Exception as e:
        status_lbl.config(text=f"\n (X) Error durante la lectura de registros. {e}")
        polling_wndw.withdraw()

# close_log_session
# Desacopla el log para permitir el acceso a otros sofwares.
def close_log_session():
    log_disengage = client.read_holding_registers(0xC34F,1,slave_address).registers[0] & 0xFF00
    client.write_register(0xC34F,log_disengage,slave_address)

# retlog_shark270
# Esta función accede a los logs y los recupera, exportando un archivo .csv en la carpeta "ExportedLogs"
# que se encuentra en el mismo directorio que el archivo .py, si la carpeta no existe la crea.
# La secuencia de recuperación sigue los pasos de Modbus "Shark-270-Meter-Modbus-Protocol-Application-Guide_E159718, sección 3"
# # Parámetros:
# log - Histórico a recuperar
def retlog_shark270(log):
    try:
        # Verificar que el medidor esté disponible para una lectura
        meter_availability = client.read_holding_registers(0xC34B,1,slave_address).registers[0]
        if(meter_availability == 0 or meter_availability == 0x0B00):            
            client.write_register(0xC34B,0x000B,slave_address)
            meter_availability = client.read_holding_registers(0xC34B,1,slave_address).registers[0]
            if(meter_availability != 0x0B00): # El medidor realiza un shift automaticamente (<< 4)
                status_lbl.config(text=f"\n /!\\ El medidor está ocupado en otra sesión.")
            else:
                status_lbl.config(text=f"\n (!) Sesión de recuperación iniciada.")

                # Obtener estado del log
                if (log == "Historic 1"):
                    log_status_block_address = 0xC757
                    log_availability_address = 0xC75C
                    log_setup_address = 0x84CF
                    log_number = 2
                elif (log == "Historic 2"):
                    log_status_block_address = 0xC767
                    log_availability_address = 0xC76C
                    log_setup_address = 0x858F
                    log_number = 3
                elif (log == "Historic 3"):
                    log_status_block_address = 0xC777
                    log_availability_address = 0xC77C
                    log_setup_address = 0x864F
                    log_number = 4
                elif (log == "Historic 4"):
                    log_status_block_address = 0xC787
                    log_availability_address = 0xC78C
                    log_setup_address = 0x870F
                    log_number = 5
                elif (log == "Historic 5"):
                    log_status_block_address = 0xC797
                    log_availability_address = 0xC79C
                    log_setup_address = 0x87CF
                    log_number = 6
                elif (log == "Historic 6"):
                    log_status_block_address = 0xC7A7
                    log_availability_address = 0xC7AC
                    log_setup_address = 0x888F
                    log_number = 7
                

                log_status_block = client.read_holding_registers(log_status_block_address,16,slave_address).registers
                log_size_rec = reg2var(log_status_block[0:2],"UINT32")
                number_rec_used = reg2var(log_status_block[2:4],"UINT32")
                rec_size_bytes = reg2var(log_status_block[4],"UINT16")
                log_availability = reg2var(log_status_block[5],"UINT16")
                first_rec_tstamp = reg2var(log_status_block[6:9],"TSTAMP")
                last_rec_tstamp = reg2var(log_status_block[9:12],"TSTAMP")
                # 4 registros vacios al final
                
                # Verificar que el log esté disponible
                if(log_availability == 0 ):
                    # Acoplar log
                    enable = 1
                    scope = 0 # Normal record

                    packed_log_engage = struct.pack('>h',log_number << 8 | enable << 7 | scope)
                    packed_log_engage = struct.unpack('>h',packed_log_engage)[0]
                    client.write_register(0xC34F,packed_log_engage,slave_address)
                    
                    # Revisar que se haya acoplado correctamente
                    log_availability = client.read_holding_registers(log_availability_address,1,slave_address).registers[0]
                    
                    if(log_availability == 0):
                        status_lbl.config(text=f"\n /!\\ El log no se ha acoplado correctamente.")
                        ret_log_wndw.withdraw()
                    else:
                        # Revisar log setup
                        log_reg_per_rec = client.read_holding_registers(log_setup_address,1,slave_address).registers[0]
                        log_reg_per_rec = (log_reg_per_rec & 0xFF00) >> 8
                        
                        historic_vars = client.read_holding_registers(log_setup_address+2,log_reg_per_rec,slave_address).registers

                        rec_titles = ['Timestamp']
                        rec_var_sizes = [3]
                        rec_var_types = ['TSTAMP']

                        for reg in historic_vars:
                            table_reg_num = reg+1
                            try:
                                var_name = reg_table.loc[reg_table['Reg#'] == table_reg_num,'Description'].values[0]
                                var_size = reg_table.loc[reg_table['Reg#'] == table_reg_num,'Size'].values[0]
                                var_type = reg_table.loc[reg_table['Reg#'] == table_reg_num,'Format'].values[0]
                                
                                if table_reg_num in [18018,18082,18146,18210,18274,18338,18402,18465,18528,18591,18654,18717,18780,18843,18906,18969,19032,19095]:
                                    # Caso especial armónicos y samples
                                    rec_titles.extend([f"{var_name} ({n})" for n in range(1,var_size+1)])
                                    rec_var_sizes.extend([1]*(var_size))
                                    rec_var_types.extend([var_type]*var_size)

                                else:
                                    # Caso normal
                                    rec_titles.append(var_name)
                                    rec_var_sizes.append(var_size)
                                    rec_var_types.append(var_type)
                            except:
                                status_lbl.config(text=f"\n /!\\ Número de registro [{reg+1}] no encontrado.")

                        # Obtener ventana
                        rec_per_window = 246//rec_size_bytes # División que redondea hacia abajo
                        num_repeats = 1
                        packed_rec_window = struct.pack('>h',rec_per_window << 8 | num_repeats)
                        packed_rec_window = struct.unpack('>h',packed_rec_window)[0]
                        client.write_registers(0xC350,[packed_rec_window,0,0],slave_address)

                        register_count = int(rec_per_window*(rec_size_bytes/2))

                        current_index = 0                        
                        export_file = [rec_titles]
                        cont = 0                   
                        while((number_rec_used-current_index) > rec_per_window):
                            logs_lbl.config(text=f"\nRecuperando records [{current_index+1}/{number_rec_used}]")
                            progressbar["value"] = (current_index/number_rec_used)*100
                            ret_log_wndw.update_idletasks()
                            window_offset = client.read_holding_registers(0xC351,2,slave_address).registers
                            current_index = reg2var(window_offset,"UINT32") & 0x00FFFFFF
                            window_status = reg2var(window_offset[0],"UINT16") & 0xFF00

                            # Esperar que el medidor prepara la ventana
                            while(window_status == 0xFF00):
                                window_offset = client.read_holding_registers(0xC351,1,slave_address).registers[0]
                                window_status = reg2var(window_offset,"UINT16") & 0xFF00

                            window_data = client.read_holding_registers(0XC353,register_count,slave_address).registers
                            # Dar formato para el archivo de exportacion
                            rec_data = []
                            i_data = 0
                            i_type = 0
                            while i_data < len(window_data):
                                i_type = i_type % len(rec_var_types) # Si una ventana contiene más de un record, reiniciar i_type
                                format = rec_var_types[i_type]                                
                                step = rec_var_sizes[i_type]

                                # Separa cada record en una nueva linea del CSV
                                if (i_type == 0 and i_data != 0):
                                    export_file.append(rec_data)
                                    rec_data = []
                                    i_type = 0

                                if step != 1:
                                    bytes = window_data[i_data:i_data+step]
                                else:                                    
                                    bytes = window_data[i_data]

                                try:
                                    value = reg2var(bytes,format)          
                                    if pd.isna(value):
                                        value = 'NaN'
                                    elif ('%' in rec_titles[i_type]) or ('Phase' in rec_titles[i_type]):
                                        value = value/100
                                        
                                    rec_data.append(value)
                                
                                except:
                                    # El registro contiene varias variables del mismo tipo
                                    for byte in bytes:
                                        value = reg2var(byte,format)
                                        if pd.isna(value):
                                            value = 'NaN'
                                        elif '%' in rec_titles[i_type]:
                                            value = value/100                                    
                                        rec_data.append(value)
                                        
                                i_data += step
                                i_type += 1
                            
                                                      
                            export_file.append(rec_data)
                            rec_data = []                        

                            # Descomentar ciclo if para obtener cierta cantidad de records, en lugar del log completo.
                            '''if(cont < 10):
                                cont += 1
                            else:
                                break'''
                            
                        logs_lbl.config(text=f"\nLog recuperado.")

                        close_log_session()

                        # Exportar el archivo
                        x = 0
                        try:
                            os.makedirs("ExportedLogs", exist_ok=True)                         
                            pd.DataFrame(export_file).to_csv(f"ExportedLogs/{meter_SN.strip()}_{log}.csv",index=False,header=False)
                            status_lbl.config(text=f"\n (!) El archivo fue exportado como {meter_SN.strip()}_{log}.csv")
                        except:                            
                            while(True):
                                try:         
                                    pd.DataFrame(export_file).to_csv(f"ExportedLogs/{meter_SN.strip()}_{log}_{x}.csv",index=False,header=False)
                                    status_lbl.config(text=f"\n (!) El archivo fue exportado como {meter_SN.strip()}_{log}_{x}.csv")
                                    break
                                except:                                                     
                                    x += 1


                else:
                    close_log_session()
                    status_lbl.config(text=f"\n /!\\ El log seleccionado está ocupado por COM{log_availability}.")
                    ret_log_wndw.withdraw()


        else:
            status_lbl.config(text=f"\n /!\\ El medidor está ocupado.")
            close_log_session()

    except Exception as e:
        close_log_session()
        status_lbl.config(text=f"\n (X) No se pudo recuperar el log. {e}")
        ret_log_wndw.withdraw()

# cancel_retlog_shark270
# Termina la sesión y cierra la ventana ret_log_wndw.
def cancel_retlog_shark270():
    close_log_session()
    status_lbl.config(text=f"\n (!) Sesión de recuperación cancelada.")
    ret_log_wndw.withdraw()

def open_log_file():
    archivo = filedialog.askopenfilename(
        title="Seleccionar archivo",
        filetypes=(("Archivos de texto", "*.csv"), ("Todos los archivos", "*.*")),
        initialdir="ExportedLogs"
    )
    if archivo:
        try:
            if os.path.exists(archivo):
                subprocess.run(["start", "excel", archivo], shell=True)
            else:
                status_lbl.config(text=f"El archivo {archivo} no existe.")
        except Exception as e:
            status_lbl.config(text=f"Error al intentar abrir el archivo con Excel: {e}")



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

return_data_lbl = tk.Text(polling_wndw, width=50)
return_data_lbl.grid(row=5,columnspan=2,sticky="w")
scrollbar = tk.Scrollbar(polling_wndw, command=return_data_lbl.yview)
scrollbar.grid(rowspan=5,column=2)
return_data_lbl.config(yscrollcommand=scrollbar.set)

# -----------------------------------     Ventana ret logs     -----------------------------------
ret_log_wndw = tk.Tk()
ret_log_wndw.title("Retrieve Log")
ret_log_wndw.withdraw()

ret_log_lbl = tk.Label(ret_log_wndw,text='Log Retrival')
ret_log_lbl.grid(row=0,columnspan=2)

log_sel_lbl = tk.Label(ret_log_wndw,text='Select log')
log_sel_lbl.grid(row=1,column=0)

log_selection = tk.StringVar(ret_log_wndw)
log_selection.set("Historic 1")
log_list = tk.OptionMenu(ret_log_wndw,log_selection,*["Historic 1","Historic 2","Historic 3","Historic 4","Historic 5","Historic 6"])
log_list.grid(row=1,column=1)

read_btn = tk.Button(ret_log_wndw, text="Retrieve",command=lambda: retlog_shark270(log_selection.get()))
read_btn.grid(row=2,column=0)

cancel_retlog_btn = tk.Button(ret_log_wndw, text="Cancel", command=lambda: cancel_retlog_shark270())
cancel_retlog_btn.grid(row=2,column=1)

logs_lbl = tk.Label(ret_log_wndw,text='\n',justify="left")
logs_lbl.grid(row=3,columnspan=2)

progressbar = ttk.Progressbar(ret_log_wndw,orient='horizontal',length=200,mode='determinate')
progressbar.grid(row=4,columnspan=2)


# -----------------------------------     Ventana principal (Cinta de opciones)     -----------------------------------
main_wndw = tk.Tk()
main_wndw.title("Shark® 270 | MODBUS TCP")

status_lbl = tk.Label(main_wndw,text="\nStatus...",justify="left")
status_lbl.grid(row=1,column=0,columnspan=10,sticky="w")

ret_log_btn = tk.Button(main_wndw, text="Ret Log",state="disabled", command=ret_log_wndw.deiconify)
ret_log_btn.grid(row=0, column=1)
open_log_btn = tk.Button(main_wndw, text="Open Log", command=lambda: open_log_file())
open_log_btn.grid(row=0, column=2)
connect_btn = tk.Button(main_wndw, text="Connect", command=connect_wndw.deiconify)
connect_btn.grid(row=0, column=5)
dis_cnct_btn = tk.Button(main_wndw, text="Dis-cnct",state="disabled", command=lambda: disconnect_shark270())
dis_cnct_btn.grid(row=0, column=6)
polling_btn = tk.Button(main_wndw, text="Polling", state="disabled", command=polling_wndw.deiconify)
polling_btn.grid(row=0, column=7)


# Ejecutar la aplicación
main_wndw.mainloop()
