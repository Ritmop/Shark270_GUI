import struct

# Array de 3 elementos (ejemplo)
array = [0x1234, 0x5678, 0x9ABC]

# Paso 1: Convertir cada elemento a su representación binaria (16 bits cada uno)
binary_elements = [struct.pack('>H', elem) for elem in array]

# Paso 2: Desempaquetar los elementos para obtener sus valores enteros
unpacked_elements = [struct.unpack('>H', elem)[0] for elem in binary_elements]

# Paso 3: Combinar los elementos en un solo número binario (48 bits)
combined_value = (unpacked_elements[0] << 32) | (unpacked_elements[1] << 16) | unpacked_elements[2]

# Paso 4: Empacar el resultado combinado en formato binario (48 bits)
# Dado que struct.pack no soporta directamente 48 bits, lo empacamos como 6 bytes
packed_result = struct.pack('>Q', combined_value)[2:]  # '>Q' empaca como 64 bits, y tomamos los 6 bytes menos significativos

# Ver los resultados
print(f"Elementos binarios: {[elem.hex() for elem in binary_elements]}")
print(f"Elementos desempaquetados: {unpacked_elements}")
print(f"Valor combinado: {combined_value:#018x}")  # Formato hexadecimal con ceros iniciales
print(f"Resultado empaquetado: {packed_result.hex()}")
