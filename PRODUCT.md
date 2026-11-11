# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The interface is a local web UI packaged for macOS with Tauri. The design language is the web UI inside that window, not a separate AppKit skin. Inferred from the brief: the user asked for a macOS application built with React, TypeScript, and Tauri.

## Stack

Confirmed by the brief, not chosen here:

- Python 3.12+ backend
- FastAPI on the local machine
- SQLite
- React and TypeScript
- Tauri for the macOS package
- macOS Keychain for sensitive credentials, with an encrypted local file when Keychain is unavailable
- pytest, plus frontend unit tests

## Users

Adam, using a personal Amazon.com account on a Mac (including Apple Silicon machines such as a MacBook Pro M3 or Mac Mini M4). The job is to see recent purchases, notice a later public price drop, and decide whether to ask about a price adjustment or a return. Inferred: one local user in the first version. The data model keeps a user id so later accounts do not require a new schema.

## Product Purpose

Track purchased products and show, when a permitted price source has actually been checked, whether the current equivalent offer is lower than the price paid. Prepare information the user can review. Success means the user can trust that a number on screen came from imported data or a labeled sample, and that the app has not submitted a return, order, refund claim, or customer-service message.

## Positioning

The app refuses to log into Amazon, refuses to store an Amazon password, and refuses to send a financially consequential action without an explicit confirmation that this version does not even offer. Savings are estimates from comparable offers, not promised refunds.

## Operating Context

Used at a desk on a Mac that is turned on. Order history enters later as a file the user downloads from Amazon. Price data, when a provider is configured in a later phase, comes from that provider's API under its rate limits. Phase 1 has no Amazon session and does not call Keepa.

## Capabilities and Constraints

In this version:

- Local SQLite database for orders, items, price snapshots, alerts, refund-request rows, notifications, and settings
- Labeled sample orders for development, clearly marked, with no claim that Amazon was contacted
- Manual price check against the sample source only
- Settings for monitoring interval, savings threshold, and notification preferences
- Secret storage for a Keepa API key name only; the key is not sent anywhere in this version
- Delete all locally stored purchase data
- Dashboard, orders, monitoring, refund assistant, returns, savings history, and settings screens

Not in this version, and must not be fabricated:

- A live Amazon connection or the user's real last 30 orders
- Keepa or other network price calls
- Refund-message drafting, submission, or refund results
- Return, repurchase, or customer-service submission
- Payment processing, subscription billing, or cloud hosting
- macOS Notification Center delivery and launchd installation

Durable constraints from the brief:

- Never ask for or store an Amazon password
- Never bypass CAPTCHA, MFA, rate limits, or Amazon security controls
- Never present a refund as guaranteed
- Never submit a return, order, purchase, refund claim, or other financially consequential action without explicit confirmation
- Do not silently transmit order history to third parties
- Do not store credit card numbers
- Logs must not contain secrets or purchase details beyond operational events

## Brand Commitments

The product name is Amazon Price Tracker & Refund Assistant. Voice is plain and specific. Amazon is the store being monitored, not an endorsement and not a login. No other brand assets were provided.

## Evidence on Hand

No Amazon export, API key, or account session is in the repository. Sample orders are synthetic. Confirmed refunds in this version are zero because none have been recorded by the user. Do not invent successful Amazon connectivity or refund outcomes.

## Product Principles

- Show the source of every price and the time it was checked.
- Treat a different seller or condition as a different offer.
- Keep actions that move money in the user's hands.
- Keep secrets out of the database, the logs, and the screen.
- Shape the local app so a later multi-user service can reuse the same records and provider interfaces.

## Accessibility & Inclusion

The interface is in English, keyboard reachable, and readable at desktop and narrow widths. Body text meets ordinary contrast expectations. No other accessibility requirement was specified.
