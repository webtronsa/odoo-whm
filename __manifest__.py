# -*- coding: utf-8 -*-
{
    "name": "WHM Hosting Management - Complete WHMCS Alternative",
    "version": "19.0.1.0",
    "summary": "Complete WHMCS alternative with WHM/cPanel hosting automation and billing",
    "description": (
        "Professional WHM/cPanel hosting management solution for Odoo 19. "
        "Automated account provisioning, domain management, billing integration, "
        "customer portal, and reseller functionality. Replicates WHMCS features "
        "including automated setup, suspension/unsuspension, usage monitoring, "
        "and comprehensive customer self-service portal."
    ),
    "category": "Website/Hosting",
    "author": "WHM Hosting Solutions",
    "website": "https://www.whmhosting.com",
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",

    # -----------------------------
    # DEPENDENCIES
    # -----------------------------
    "depends": [
        "base",
        "mail",
        "portal",
        "website",
        "helpdesk",
        "sale",
        "sale_management",
        "product",
        "payment",
        "contacts",
        "account",
    ],

    # -----------------------------
    # DATA FILES
    # -----------------------------
    "data": [
        # Security
        "security/ir.model.access.csv",
        "security/whm_security.xml",

        # Backend menus
        "views/whm_backend_menu.xml",

        # Core backend views
        "views/whm_hosting_views.xml",
        "views/whm_domain_views.xml",
        "views/whm_package_views.xml",
        "views/whm_server_views.xml",
        "views/whm_tld_views.xml",
        "views/product_views.xml",

        # Portal templates
        "views/portal_templates.xml",
        "views/portal_hosting_setup.xml",

        # Email templates
        "views/email_templates.xml",

        # Scheduled jobs
        "data/crons.xml",
        "data/whm_data.xml",
    ],

    # -----------------------------
    # ASSETS
    # -----------------------------
    "assets": {
        "web.assets_frontend": [
            "whm_hosting/static/src/scss/portal.scss",
            "whm_hosting/static/src/js/portal.js",
        ],
        "web.assets_backend": [
            "whm_hosting/static/src/scss/backend.scss",
            "whm_hosting/static/src/js/backend.js",
        ],
    },

    # -----------------------------
    # DEMO DATA
    # -----------------------------
    "demo": [
        "data/whm_demo.xml",
    ],
}
