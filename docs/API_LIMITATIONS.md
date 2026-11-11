# Price and order sources

This version does not call Amazon, Keepa, or any other network price service. A manual check uses the labeled sample catalog shipped with the app.

## Orders

Amazon does not offer a consumer API for a buyer's personal order history. The Selling Partner API is for sellers looking at orders placed with them, and it is not a way to read a personal Amazon account.

The supported path for real orders is a file the account holder downloads themselves (an order-history report or a personal-data export) and imports locally. That importer is not in this version. Until it exists, the only orders in the app are the six labeled samples, and only after you load them.

The app will not ask for an Amazon password, will not store one, and will not drive a browser session through login, CAPTCHA, or MFA.

## Prices

Keepa is a separate paid product, not an Amazon API. Plans are token budgets sold by Keepa, and the prices change. Hourly checks of many products can spend a small plan's tokens before the day is over. This version can store a Keepa key and does not send it anywhere. When a later version calls Keepa, it has to stop when the token budget says so and show the time of the last successful check.

Amazon's Product Advertising API is an affiliate catalog. It is not a purchase-history API and it is not wired up here.

Public page scraping is not a source this app will use.

## Refunds

Amazon does not generally promise a price adjustment after you buy. A lower comparable total in this app is an estimate, not a refund, and not a promise that a request would be accepted. This version does not draft or send a customer-service message.

## Returns

The repurchase line is arithmetic: comparable savings, minus the restocking fee and return shipping you set. Both fees default to zero. The app cannot see Amazon's live return rules. It will not start a return, a replacement order, or a refund claim.
