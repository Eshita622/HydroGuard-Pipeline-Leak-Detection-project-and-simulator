import {
  pgTable,
  text,
  real,
  integer,
  boolean,
  timestamp,
} from "drizzle-orm/pg-core";

export const hydroChampionsTable = pgTable("hydro_champions", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  phone: text("phone").notNull(),
  assignedZone: text("assigned_zone").notNull(),
  status: text("status").notNull().default("available"),
  averageResponseMinutes: real("average_response_minutes").notNull().default(0),
  userId: text("user_id"),
});

export const hydroAlertsTable = pgTable("hydro_alerts", {
  id: text("id").primaryKey(),
  zone: text("zone").notNull(),
  location: text("location").notNull(),
  sensorId: text("sensor_id").notNull(),
  type: text("type").notNull(),
  severity: text("severity").notNull(),
  flowLpm: real("flow_lpm").notNull(),
  pressureBar: real("pressure_bar").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  status: text("status").notNull(),
  championId: text("champion_id"),
});

export const hydroMaintenanceTable = pgTable("hydro_maintenance", {
  id: text("id").primaryKey(),
  maintenanceId: text("maintenance_id").notNull().unique(),
  pipeline: text("pipeline").notNull(),
  location: text("location").notNull(),
  issue: text("issue").notNull(),
  championId: text("champion_id"),
  priority: text("priority").notNull(),
  startedAt: timestamp("started_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
  status: text("status").notNull(),
  alertId: text("alert_id"),
});

export const hydroSmsHistoryTable = pgTable("hydro_sms_history", {
  id: text("id").primaryKey(),
  recipient: text("recipient").notNull(),
  alertId: text("alert_id").notNull(),
  message: text("message").notNull(),
  sentAt: timestamp("sent_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  status: text("status").notNull(),
  mode: text("mode").notNull(),
});

export const hydroSettingsTable = pgTable("hydro_settings", {
  id: text("id").primaryKey(),
  flowWarningThreshold: real("flow_warning_threshold").notNull(),
  flowLeakThreshold: real("flow_leak_threshold").notNull(),
  pressureWarningThreshold: real("pressure_warning_threshold").notNull(),
  pressureCriticalThreshold: real("pressure_critical_threshold").notNull(),
  smsMode: text("sms_mode").notNull().default("demo"),
  smsProviderConnected: boolean("sms_provider_connected")
    .notNull()
    .default(false),
});

export const hydroDevicesTable = pgTable("hydro_devices", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  location: text("location").notNull(),
  status: text("status").notNull(),
  lastSeen: timestamp("last_seen", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const hydroAuthRateLimitsTable = pgTable("hydro_auth_rate_limits", {
  key: text("key").primaryKey(),
  attempts: integer("attempts").notNull().default(0),
  windowStartedAt: timestamp("window_started_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});