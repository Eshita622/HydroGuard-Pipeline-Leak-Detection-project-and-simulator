import { pgTable, text, integer, timestamp } from "drizzle-orm/pg-core";

export const hydroUsersTable = pgTable("hydro_users", {
  id: text("id").primaryKey(),
  fullName: text("full_name").notNull(),
  email: text("email").notNull().unique(),
  mobile: text("mobile").notNull().unique(),
  passwordHash: text("password_hash").notNull(),
  role: text("role").notNull(),
  assignedZone: text("assigned_zone").notNull().default("Zone 1"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const hydroSessionsTable = pgTable("hydro_sessions", {
  tokenHash: text("token_hash").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => hydroUsersTable.id, { onDelete: "cascade" }),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const hydroOtpTable = pgTable("hydro_otp_codes", {
  mobile: text("mobile").primaryKey(),
  codeHash: text("code_hash").notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  attempts: integer("attempts").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});