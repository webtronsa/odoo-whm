# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # WHM Product Types
    is_whm_product = fields.Boolean(string="WHM Product", default=False)
    whm_product_type = fields.Selection([
        ("hosting", "Web Hosting"),
        ("reseller", "Reseller Hosting"),
        ("vps", "VPS Hosting"),
        ("dedicated", "Dedicated Server"),
        ("domain", "Domain Registration"),
        ("ssl", "SSL Certificate"),
        ("addon", "Addon Service"),
    ], string="WHM Product Type")

    # Hosting Configuration
    whm_package_id = fields.Many2one("whm.package", string="WHM Package")
    whm_server_id = fields.Many2one("whm.server", string="Default Server")
    whm_tld_id = fields.Many2one("whm.tld", string="TLD (for domains)")
    
    # Billing Configuration
    whm_setup_fee = fields.Float(string="WHM Setup Fee", default=0.0)
    whm_pricing_model = fields.Selection([
        ("fixed", "Fixed Price"),
        ("usage_based", "Usage Based"),
        ("tiered", "Tiered Pricing"),
    ], default="fixed", string="WHM Pricing Model")
    
    # Domain Configuration
    whm_domain_registration = fields.Boolean(string="Domain Registration", default=False)
    whm_domain_transfer = fields.Boolean(string="Domain Transfer", default=False)
    whm_domain_renewal = fields.Boolean(string="Domain Renewal", default=False)
    
    # SSL Configuration
    whm_ssl_type = fields.Selection([
        ("standard", "Standard SSL"),
        ("wildcard", "Wildcard SSL"),
        ("ev", "Extended Validation SSL"),
        ("multi_domain", "Multi-Domain SSL"),
    ], string="SSL Type")
    
    # Service Configuration
    whm_auto_provision = fields.Boolean(string="Auto Provision", default=True)
    whm_auto_setup = fields.Boolean(string="Auto Setup", default=True)
    whm_trial_days = fields.Integer(string="Trial Days", default=0)
    
    # Limits and Quotas
    whm_max_accounts_per_customer = fields.Integer(string="Max Accounts per Customer", default=1)
    whm_min_contract_period = fields.Integer(string="Min Contract Period (Months)", default=1)
    whm_cancellation_notice_days = fields.Integer(string="Cancellation Notice (Days)", default=30)
    
    # Integration Settings
    whm_sync_with_whm = fields.Boolean(string="Sync with WHM", default=True)
    whm_create_package_in_whm = fields.Boolean(string="Create Package in WHM", default=False)

    @api.depends('whm_product_type')
    def _compute_is_whm_product(self):
        """Automatically set is_whm_product based on type"""
        for template in self:
            template.is_whm_product = bool(template.whm_product_type)

    @api.onchange('whm_product_type')
    def _onchange_whm_product_type(self):
        """Update default values based on product type"""
        if self.whm_product_type == 'hosting':
            self.type = 'service'
            self.recurring_invoice = True
            self.service_type = 'manual'
        elif self.whm_product_type == 'domain':
            self.type = 'service'
            self.recurring_invoice = False
            self.service_type = 'manual'
        elif self.whm_product_type == 'ssl':
            self.type = 'service'
            self.recurring_invoice = True
            self.service_type = 'manual'

    def create_whm_hosting_account(self, partner, sale_order_line=None):
        """Create WHM hosting account from product template"""
        self.ensure_one()
        
        # Use the first product variant
        product = self.product_variant_ids[:1]
        if not product:
            raise UserError(_("No product variant found"))
        
        return product.create_whm_hosting_account(partner, sale_order_line)

    def get_whm_pricing(self, billing_cycle='monthly'):
        """Get WHM pricing for specific billing cycle"""
        self.ensure_one()
        
        # Use the first product variant for pricing
        product = self.product_variant_ids[:1]
        if product:
            return product.get_whm_pricing(billing_cycle)
        
        return 0.0

    def sync_whm_package(self):
        """Sync product template with WHM package"""
        self.ensure_one()
        
        # Use the first product variant
        product = self.product_variant_ids[:1]
        if product:
            return product.sync_whm_package()
        
        raise UserError(_("No product variant found"))

    @api.model
    def create_whm_domain_product(self, tld, registrar=None):
        """Create a domain registration product for TLD"""
        product_vals = {
            'name': f"Domain Registration - .{tld.name}",
            'type': 'service',
            'whm_product_type': 'domain',
            'whm_tld_id': tld.id,
            'whm_domain_registration': True,
            'list_price': tld.registration_price,
            'standard_price': tld.registration_price,
            'sale_ok': True,
            'purchase_ok': False,
            'recurring_invoice': False,
            'service_type': 'manual',
            'is_whm_product': True,
        }
        
        return self.create(product_vals)

    def get_whm_product_summary(self):
        """Get summary of WHM product configuration"""
        self.ensure_one()
        
        if not self.is_whm_product:
            return _("Not a WHM product")
        
        summary_parts = []
        
        # Product type
        summary_parts.append(f"Type: {dict(self._fields['whm_product_type'].selection).get(self.whm_product_type, 'Unknown')}")
        
        # Package info
        if self.whm_package_id:
            summary_parts.append(f"Package: {self.whm_package_id.name}")
        
        # Server info
        if self.whm_server_id:
            summary_parts.append(f"Server: {self.whm_server_id.name}")
        
        # Pricing
        if self.whm_setup_fee:
            summary_parts.append(f"Setup Fee: ${self.whm_setup_fee}")
        
        # Auto-provisioning
        if self.whm_auto_provision:
            summary_parts.append("Auto-Provision: Enabled")
        
        return " • ".join(summary_parts) if summary_parts else _("Basic WHM Product")

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('whm_product_type')
    def _check_whm_product_configuration(self):
        for template in self:
            if template.is_whm_product:
                if template.whm_product_type in ['hosting', 'reseller'] and not template.whm_package_id:
                    raise ValidationError(_("WHM package is required for hosting products"))
                
                if template.whm_product_type == 'domain' and not template.whm_tld_id:
                    raise ValidationError(_("TLD is required for domain products"))

    @api.constrains('whm_setup_fee', 'list_price')
    def _check_whm_pricing(self):
        for template in self:
            if template.is_whm_product:
                if template.whm_setup_fee < 0:
                    raise ValidationError(_("WHM setup fee cannot be negative"))
                
                if template.list_price < 0 and template.whm_product_type != 'addon':
                    raise ValidationError(_("List price cannot be negative for WHM products"))

    # --------------------------------------------------
    # NAME GET METHOD
    # --------------------------------------------------

    def name_get(self):
        result = []
        for template in self:
            display_name = template.name
            if template.is_whm_product:
                type_label = dict(template._fields['whm_product_type'].selection).get(
                    template.whm_product_type, 'WHM'
                )
                display_name = f"{template.name} [{type_label}]"
            result.append((template.id, display_name))
        return result
