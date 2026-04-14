# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    # WHM Customer Information
    whm_customer_id = fields.Char(string="WHM Customer ID", readonly=True)
    whm_customer_type = fields.Selection([
        ("individual", "Individual"),
        ("business", "Business"),
        ("reseller", "Reseller"),
    ], string="WHM Customer Type", default="individual")
    
    # WHM Preferences
    whm_preferred_server = fields.Many2one("whm.server", string="Preferred Server")
    whm_preferred_package = fields.Many2one("whm.package", string="Preferred Package")
    whm_auto_setup_domains = fields.Boolean(string="Auto Setup Domains", default=True)
    whm_enable_notifications = fields.Boolean(string="Enable WHM Notifications", default=True)
    
    # Billing Information
    whm_billing_method = fields.Selection([
        ("invoice", "Invoice"),
        ("credit_card", "Credit Card"),
        ("paypal", "PayPal"),
        ("bank_transfer", "Bank Transfer"),
    ], string="WHM Billing Method", default="invoice")
    
    whm_credit_limit = fields.Float(string="WHM Credit Limit", default=0.0)
    whm_current_balance = fields.Float(string="WHM Current Balance", default=0.0)
    
    # WHM Account Limits
    whm_max_hosting_accounts = fields.Integer(string="Max Hosting Accounts", default=0,
                                           help="0 = unlimited")
    whm_max_domains = fields.Integer(string="Max Domains", default=0,
                                   help="0 = unlimited")
    whm_max_ssl_certificates = fields.Integer(string="Max SSL Certificates", default=0,
                                            help="0 = unlimited")
    
    # Relations
    whm_hosting_account_ids = fields.One2many("whm.hosting.account", "partner_id", 
                                            string="Hosting Accounts")
    whm_domain_ids = fields.One2many("whm.domain", compute="_compute_whm_domains")
    
    # Statistics
    whm_account_count = fields.Integer(string="WHM Account Count", compute="_compute_whm_stats")
    whm_active_account_count = fields.Integer(string="Active Accounts", compute="_compute_whm_stats")
    whm_domain_count = fields.Integer(string="Domain Count", compute="_compute_whm_stats")
    whm_total_monthly_cost = fields.Float(string="Total Monthly Cost", compute="_compute_whm_stats")
    
    # Status
    whm_is_active_customer = fields.Boolean(string="Active WHM Customer", compute="_compute_whm_status")
    whm_last_activity = fields.Datetime(string="Last WHM Activity", compute="_compute_whm_last_activity")

    @api.depends('whm_hosting_account_ids')
    def _compute_whm_domains(self):
        for partner in self:
            partner.whm_domain_ids = self.env['whm.domain'].search([
                ('hosting_account_id.partner_id', '=', partner.id)
            ])

    @api.depends('whm_hosting_account_ids')
    def _compute_whm_stats(self):
        for partner in self:
            accounts = partner.whm_hosting_account_ids
            partner.whm_account_count = len(accounts)
            partner.whm_active_account_count = len(accounts.filtered(lambda a: a.state == 'active'))
            partner.whm_domain_count = len(partner.whm_domain_ids)
            
            # Calculate total monthly cost
            total_monthly = sum(
                account.recurring_amount for account in accounts 
                if account.state == 'active' and account.billing_cycle == 'monthly'
            )
            partner.whm_total_monthly_cost = total_monthly

    @api.depends('whm_hosting_account_ids.state')
    def _compute_whm_status(self):
        for partner in self:
            active_accounts = partner.whm_hosting_account_ids.filtered(
                lambda a: a.state in ['active', 'suspended']
            )
            partner.whm_is_active_customer = bool(active_accounts)

    @api.depends('whm_hosting_account_ids.write_date')
    def _compute_whm_last_activity(self):
        for partner in self:
            accounts = partner.whm_hosting_account_ids
            if accounts:
                partner.whm_last_activity = max(accounts.mapped('write_date'))
            else:
                partner.whm_last_activity = False

    # --------------------------------------------------
    # WHM CUSTOMER ACTIONS
    # --------------------------------------------------

    def action_create_whm_customer(self):
        """Create WHM customer account"""
        self.ensure_one()
        
        if self.whm_customer_id:
            raise UserError(_("WHM customer already exists for this partner"))
        
        # This would integrate with WHM customer creation API
        # For now, just generate a customer ID
        import uuid
        customer_id = f"whm_{uuid.uuid4().hex[:8]}"
        
        self.write({
            'whm_customer_id': customer_id,
        })
        
        self.message_post(body=_(
            "<b>✅ WHM Customer Created</b><br/>"
            "Customer ID: %s"
        ) % customer_id)

    def action_view_whm_accounts(self):
        """View WHM hosting accounts for this customer"""
        self.ensure_one()
        
        if not self.whm_hosting_account_ids:
            raise UserError(_("No WHM hosting accounts found for this customer"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'WHM Hosting Accounts',
            'res_model': 'whm.hosting.account',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_whm_domains(self):
        """View WHM domains for this customer"""
        self.ensure_one()
        
        if not self.whm_domain_ids:
            raise UserError(_("No WHM domains found for this customer"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'WHM Domains',
            'res_model': 'whm.domain',
            'view_mode': 'tree,form',
            'domain': [('hosting_account_id.partner_id', '=', self.id)],
        }

    def action_suspend_all_accounts(self):
        """Suspend all active WHM accounts for this customer"""
        self.ensure_one()
        
        active_accounts = self.whm_hosting_account_ids.filtered(
            lambda a: a.state == 'active'
        )
        
        if not active_accounts:
            raise UserError(_("No active accounts to suspend"))
        
        suspended_count = 0
        for account in active_accounts:
            try:
                account.action_suspend()
                suspended_count += 1
            except Exception as e:
                _logger.error("Failed to suspend account %s: %s", account.name, str(e))
        
        self.message_post(body=_(
            "<b>🔒 Accounts Suspended</b><br/>"
            "Suspended %d out of %d active accounts"
        ) % (suspended_count, len(active_accounts)))

    def action_unsuspend_all_accounts(self):
        """Unsuspend all suspended WHM accounts for this customer"""
        self.ensure_one()
        
        suspended_accounts = self.whm_hosting_account_ids.filtered(
            lambda a: a.state == 'suspended'
        )
        
        if not suspended_accounts:
            raise UserError(_("No suspended accounts to unsuspend"))
        
        unsuspended_count = 0
        for account in suspended_accounts:
            try:
                account.action_unsuspend()
                unsuspended_count += 1
            except Exception as e:
                _logger.error("Failed to unsuspend account %s: %s", account.name, str(e))
        
        self.message_post(body=_(
            "<b>🔓 Accounts Unsuspended</b><br/>"
            "Unsuspended %d out of %d suspended accounts"
        ) % (unsuspended_count, len(suspended_accounts)))

    # --------------------------------------------------
    # BILLING AND CREDIT MANAGEMENT
    # --------------------------------------------------

    def update_whm_balance(self, amount, description=""):
        """Update WHM balance for customer"""
        self.ensure_one()
        
        new_balance = self.whm_current_balance + amount
        self.write({'whm_current_balance': new_balance})
        
        # Create transaction record (would need a separate model)
        self.message_post(body=_(
            "<b>💰 Balance Updated</b><br/>"
            "Amount: $%.2f<br/>"
            "New Balance: $%.2f<br/>"
            "Description: %s"
        ) % (amount, new_balance, description))

    def check_credit_limit(self, additional_amount=0):
        """Check if customer has sufficient credit"""
        self.ensure_one()
        
        if self.whm_credit_limit <= 0:
            return True  # No credit limit set
        
        total_balance = self.whm_current_balance + additional_amount
        return total_balance <= self.whm_credit_limit

    def get_whm_billing_summary(self):
        """Get billing summary for WHM services"""
        self.ensure_one()
        
        summary = {
            'monthly_cost': self.whm_total_monthly_cost,
            'current_balance': self.whm_current_balance,
            'credit_limit': self.whm_credit_limit,
            'available_credit': self.whm_credit_limit - self.whm_current_balance,
            'account_count': self.whm_account_count,
            'active_accounts': self.whm_active_account_count,
            'domain_count': self.whm_domain_count,
        }
        
        return summary

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    @api.constrains('whm_max_hosting_accounts', 'whm_max_domains', 'whm_max_ssl_certificates')
    def _check_whm_limits(self):
        for partner in self:
            if partner.whm_max_hosting_accounts < 0:
                raise ValidationError(_("Max hosting accounts cannot be negative"))
            
            if partner.whm_max_domains < 0:
                raise ValidationError(_("Max domains cannot be negative"))
            
            if partner.whm_max_ssl_certificates < 0:
                raise ValidationError(_("Max SSL certificates cannot be negative"))

    @api.constrains('whm_credit_limit', 'whm_current_balance')
    def _check_whm_billing(self):
        for partner in self:
            if partner.whm_credit_limit < 0:
                raise ValidationError(_("WHM credit limit cannot be negative"))
            
            if partner.whm_current_balance < 0:
                raise ValidationError(_("WHM current balance cannot be negative"))

    # --------------------------------------------------
    # AUTOMATION
    # --------------------------------------------------

    def check_account_limits(self):
        """Check if customer exceeds account limits"""
        self.ensure_one()
        
        warnings = []
        
        if (self.whm_max_hosting_accounts > 0 and 
            self.whm_account_count >= self.whm_max_hosting_accounts):
            warnings.append(f"Hosting account limit reached ({self.whm_max_hosting_accounts})")
        
        if (self.whm_max_domains > 0 and 
            self.whm_domain_count >= self.whm_max_domains):
            warnings.append(f"Domain limit reached ({self.whm_max_domains})")
        
        return warnings

    # --------------------------------------------------
    # SEARCH AND FILTERS
    # --------------------------------------------------

    @api.model
    def _search_whm_is_active_customer(self, operator, value):
        """Custom search for active WHM customers"""
        if operator == '=' and value:
            return [('whm_hosting_account_ids.state', 'in', ['active', 'suspended'])]
        elif operator == '=' and not value:
            return [('whm_hosting_account_ids.state', 'not in', ['active', 'suspended'])]
        return []

    # --------------------------------------------------
    # NAME GET METHOD
    # --------------------------------------------------

    def name_get(self):
        result = []
        for partner in self:
            display_name = partner.name
            if partner.whm_customer_id:
                display_name = f"{partner.name} ({partner.whm_customer_id})"
            if partner.whm_is_active_customer:
                display_name = f"{display_name} [Active]"
            result.append((partner.id, display_name))
        return result
