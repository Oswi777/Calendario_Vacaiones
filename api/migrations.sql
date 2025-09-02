-- Borrar (cuidado: destruye datos)
DROP TABLE IF EXISTS vacaciones CASCADE;
DROP TABLE IF EXISTS empleados CASCADE;

-- Crear
CREATE TABLE empleados (
  id SERIAL PRIMARY KEY,
  numero_emp VARCHAR(32) UNIQUE NOT NULL,
  nombre TEXT NOT NULL,
  nombre_corto TEXT,
  area TEXT,
  turno VARCHAR(16),
  planta VARCHAR(16),
  foto_url TEXT,
  activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE vacaciones (
  id SERIAL PRIMARY KEY,
  empleado_id INT NOT NULL REFERENCES empleados(id) ON DELETE CASCADE,
  fecha_inicial DATE NOT NULL,
  fecha_final DATE NOT NULL,
  tipo VARCHAR(64) NOT NULL,
  gozo NUMERIC(4,1),
  fuente VARCHAR(16) DEFAULT 'manual'
);

CREATE INDEX idx_vacaciones_rango ON vacaciones(fecha_inicial, fecha_final);
CREATE INDEX idx_empleados_numero ON empleados(numero_emp);
