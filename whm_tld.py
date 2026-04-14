# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WHMTLD(models.Model):
    _name = "whm.tld"
    _description = "WHM Top Level Domain"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="TLD Extension", required=True, tracking=True,
                      help="TLD extension without dot, e.g., 'com', 'org', 'co.za'")
    description = fields.Char(string="Description", tracking=True)
    
    # Pricing Configuration
    registration_price = fields.Float(string="Registration Price", default=0.0, tracking=True)
    transfer_price = fields.Float(string="Transfer Price", default=0.0, tracking=True)
    renewal_price = fields.Float(string="Renewal Price", default=0.0, tracking=True)
    
    # Registration Requirements
    min_years = fields.Integer(string="Minimum Years", default=1, tracking=True)
    max_years = fields.Integer(string="Maximum Years", default=10, tracking=True)
    
    # Restrictions
    is_restricted = fields.Boolean(string="Restricted TLD", default=False, tracking=True)
    restriction_description = fields.Text(string="Restriction Description", 
                                        help="Describe any restrictions for this TLD")
    
    # DNS Requirements
    requires_glue_records = fields.Boolean(string="Requires Glue Records", default=False, tracking=True)
    nameserver_requirements = fields.Text(string="Nameserver Requirements",
                                        help="Special requirements for nameservers")
    
    # WHOIS Privacy
    whois_privacy_available = fields.Boolean(string="WHOIS Privacy Available", 
                                           default=True, tracking=True)
    whois_privacy_price = fields.Float(string="WHOIS Privacy Price", default=0.0, tracking=True)
    
    # Status
    is_active = fields.Boolean(string="Active", default=True, tracking=True)
    is_featured = fields.Boolean(string="Featured", default=False, tracking=True)
    
    # Registry Information
    registry_name = fields.Char(string="Registry Name", tracking=True)
    registry_url = fields.Char(string="Registry URL", tracking=True)
    grace_period_days = fields.Integer(string="Grace Period (Days)", default=0, tracking=True)
    redemption_period_days = fields.Integer(string="Redemption Period (Days)", default=30, tracking=True)
    
    # Integration Settings
    idn_supported = fields.Boolean(string="Internationalized Domain Names Supported", 
                                  default=True, tracking=True)
    dnssec_supported = fields.Boolean(string="DNSSEC Supported", default=True, tracking=True)
    
    # Relations
    domain_ids = fields.One2many("whm.domain", compute="_compute_domains")
    registrar_tld_ids = fields.One2many("whm.registrar.tld", "tld_id", string="Registrar TLDs")

    @api.depends('name')
    def _compute_domains(self):
        for tld in self:
            tld.domain_ids = self.env['whm.domain'].search([
                ('name', 'like', f'%.{tld.name}')
            ])

    # --------------------------------------------------
    # UTILITY METHODS
    # --------------------------------------------------

    def get_full_tld(self):
        """Get full TLD with dot prefix"""
        self.ensure_one()
        return f".{self.name}"

    def get_price_for_action(self, action, years=1):
        """Calculate price for specific action and number of years"""
        self.ensure_one()
        price_map = {
            'register': self.registration_price,
            'transfer': self.transfer_price,
            'renew': self.renewal_price,
        }
        
        base_price = price_map.get(action, 0)
        return base_price * years

    def validate_years(self, years):
        """Validate number of years for registration/renewal"""
        self.ensure_one()
        if years < self.min_years:
            raise ValidationError(_(
                "Minimum registration period for .%s is %d years"
            ) % (self.name, self.min_years))
        
        if years > self.max_years:
            raise ValidationError(_(
                "Maximum registration period for .%s is %d years"
            ) % (self.name, self.max_years))

    def check_domain_eligibility(self, domain_name):
        """Check if domain name is eligible for this TLD"""
        self.ensure_one()
        
        # Remove TLD from domain name
        if domain_name.endswith(f'.{self.name}'):
            domain_part = domain_name[:-len(f'.{self.name}')]
        else:
            domain_part = domain_name
        
        # Basic validation
        if not domain_part:
            raise ValidationError(_("Domain name cannot be empty"))
        
        if len(domain_part) < 2:
            raise ValidationError(_("Domain name must be at least 2 characters long"))
        
        if len(domain_part) > 63:
            raise ValidationError(_("Domain name cannot exceed 63 characters"))
        
        # TLD-specific restrictions can be added here
        if self.is_restricted and self.restriction_description:
            # This would typically involve checking against specific requirements
            pass
        
        return True

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('name')
    def _check_tld_name(self):
        for tld in self:
            if tld.name:
                if tld.name.startswith('.'):
                    raise ValidationError(_("TLD should not start with a dot"))
                
                # Basic TLD format validation
                import re
                if not re.match(r'^[a-zA-Z0-9\-\.]+$', tld.name):
                    raise ValidationError(_("Invalid TLD format"))

    @api.constrains('min_years', 'max_years')
    def _check_year_limits(self):
        for tld in self:
            if tld.min_years <= 0:
                raise ValidationError(_("Minimum years must be greater than 0"))
            
            if tld.max_years <= 0:
                raise ValidationError(_("Maximum years must be greater than 0"))
            
            if tld.min_years > tld.max_years:
                raise ValidationError(_("Minimum years cannot be greater than maximum years"))

    @api.constrains('registration_price', 'transfer_price', 'renewal_price', 'whois_privacy_price')
    def _check_prices(self):
        for tld in self:
            if any(getattr(tld, field) < 0 for field in [
                'registration_price', 'transfer_price', 'renewal_price', 'whois_privacy_price'
            ]):
                raise ValidationError(_("Prices cannot be negative"))

    # --------------------------------------------------
    # NAME GET METHOD
    # --------------------------------------------------

    def name_get(self):
        result = []
        for tld in self:
            display_name = f".{tld.name}"
            if tld.description:
                display_name = f".{tld.name} - {tld.description}"
            if not tld.is_active:
                display_name = f"{display_name} [Inactive]"
            result.append((tld.id, display_name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Search TLDs with or without dot prefix"""
        if args is None:
            args = []
        
        if name and name.startswith('.'):
            # Search without dot
            name_without_dot = name[1:]
            domain_ids = self._search([
                ('name', operator, name_without_dot)
            ] + args, limit=limit)
            return self.browse(domain_ids).name_get()
        
        return super().name_search(name, args, operator, limit)

    # --------------------------------------------------
    # STATISTICS
    # --------------------------------------------------

    def get_domain_count(self):
        """Get number of domains with this TLD"""
        self.ensure_one()
        return len(self.domain_ids)

    def get_active_domain_count(self):
        """Get number of active domains with this TLD"""
        self.ensure_one()
        return len(self.domain_ids.filtered(lambda d: d.state == 'active'))

    def get_expiring_soon_count(self, days=30):
        """Get number of domains expiring within specified days"""
        self.ensure_one()
        from datetime import date, timedelta
        expiry_date = date.today() + timedelta(days=days)
        
        return len(self.domain_ids.filtered(
            lambda d: d.expiry_date and d.expiry_date <= expiry_date
        ))
