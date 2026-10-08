---
name: HydroGuard authentication and notifications
description: HydroGuard's current authentication method and notification scope.
---

HydroGuard sign-in uses email or mobile as the account identifier with a password and JWT. Do not implement mobile OTP, SMS, WhatsApp, email notifications, or external notification services until the user asks.

**Why:** the user explicitly deferred all OTP and notification delivery.

**How to apply:** Keep authentication server-owned and token-based. Avoid notification routes, delivery simulations, provider setup, and notification controls in the HydroGuard app.