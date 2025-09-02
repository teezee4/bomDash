# Siemens LA Metro Train Upgrades - Inventory Management System

This is an inventory management system used by Siemens to keep track of parts and materials for the LA Metro train upgrades project. The application provides a comprehensive solution for managing the Bill of Materials (BOM), tracking deliveries, adjusting stock levels, and monitoring inventory across different divisions.

## Features

- **Dashboard:** At-a-glance view of key inventory metrics, including total parts, low stock parts, out-of-stock parts, and recent deliveries.
- **Parts List:** A comprehensive and searchable list of all parts in the BOM, with filtering options for part type and stock level.
- **Delivery Logging:** A form to log incoming deliveries, which automatically updates the stock levels of the corresponding parts.
- **Stock Adjustments:** A feature for manually adjusting stock levels with a record of each adjustment.
- **Train Calculator:** A tool to calculate the total number of parts required for a specified number of trains, highlighting any shortages.
- **User Roles:** The application supports two user roles:
    - **Viewer:** Can view all data but cannot make any changes.
    - **Admin:** Can perform all actions, including adding/editing parts, logging deliveries, and adjusting stock.
- **Division Management:** The ability to create and manage different inventory divisions, track parts sent to each division, and monitor their usage.
- **Inventory Reports:** Generate reports on low stock items, out-of-stock items, and recent inventory movements.
- **Defected Parts Log:** A system for logging and tracking defected parts.

## Technologies Used

- **Backend:** Python, Flask, Flask-SQLAlchemy, Flask-Migrate
- **Database:** PostgreSQL
- **Frontend:** HTML, CSS (with a templating engine, likely Jinja2)
- **Deployment:** Gunicorn
