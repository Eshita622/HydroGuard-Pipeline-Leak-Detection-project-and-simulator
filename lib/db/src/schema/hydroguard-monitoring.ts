import {
  pgTable,
  text,
  real,
  timestamp,
  jsonb,
} from "drizzle-orm/pg-core";

export const hydroSensorsTable = pgTable("hydro_sensors", {
  id: text("id").primaryKey(),
  sensorId: text("sensor_id").notNull().unique(),
  location: text("location").notNull(),
  flowLpm: real("flow_lpm").notNull(),
  pressureBar: real("pressure_bar").notNull(),
  tankLevelPercent: real("tank_level_percent").notNull(),
  batteryPercent: real("battery_percent").notNull(),
  status: text("status").notNull(),
  lastUpdated: timestamp("last_updated", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const hydroReadingsTable = pgTable("hydro_readings", {
  id: text("id").primaryKey(),
  sensorId: text("sensor_id").notNull(),
  flowLpm: real("flow_lpm").notNull(),
  pressureBar: real("pressure_bar").notNull(),
  tankLevelPercent: real("tank_level_percent").notNull(),
  recordedAt: timestamp("recorded_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const hydroPipelinesTable = pgTable("hydro_pipelines", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  location: text("location").notNull(),
  status: text("status").notNull(),
  flowLpm: real("flow_lpm").notNull().default(0),
  pressureBar: real("pressure_bar").notNull().default(0),
  detectedAt: timestamp("detected_at", { withTimezone: true }),
  coordinates: jsonb("coordinates")
    .$type<[number, number][]>()
    .notNull(),
  tanks: jsonb("tanks")
    .$type<{ name: string; levelPercent: number; coordinates: [number, number] }[]>()
    .notNull(),
  sensors: jsonb("sensors")
    .$type<{ sensorId: string; status: string; coordinates: [number, number] }[]>()
    .notNull(),
});