import struct

tstamp_mask = 0x7f0f1f1f3f3f  
tstamp_bytes = struct.pack('>Q',(0x1702 << 32 | 0x160E << 16 | 0))
tstamp = struct.unpack('>Q',tstamp_bytes)[0] & tstamp_mask
tstamp_str = f"{tstamp:012X}"

year = int(tstamp_str[0:2],16)
month = int(tstamp_str[2:4],16)
day = int(tstamp_str[4:6],16)
hour = int(tstamp_str[6:8],16)
minute = int(tstamp_str[8:10],16)
second = int(tstamp_str[10:12],16)

print(f"{day:02}/{month:02}/20{year:02} {hour:02}:{minute:02}:{second:02}")