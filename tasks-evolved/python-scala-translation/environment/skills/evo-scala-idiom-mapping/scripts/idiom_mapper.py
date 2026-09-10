import re
def snake_to_camel(name):
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])
def map_python_type_to_scala(py_type):
    m = {'str':'String','bytes':'Array[Byte]','int':'Int','float':'Double',
         'bool':'Boolean','Any':'Any','Decimal':'BigDecimal',
         'datetime':'LocalDateTime','date':'LocalDate'}
    return m.get(py_type, py_type)
