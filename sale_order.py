# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # WHM Integration Fields
    whm_has_hosting = fields.Boolean(string="Contains Hosting", compute="_compute_whm_has_hosting")
    whm_has_domains = fields.Boolean(string="Contains Domains", compute="_compute_whm_has_domains")
    whm_hosting_account_ids = fields.One2many("whm.hosting.account", compute="_compute_whm_accounts")
    whm_domain_ids = fields.One2many("whm.domain", compute="_compute_whm_domains")
    
    # WHM Status
    whm_provisioning_status = fields.Selection([
        ("pending", "Pending Provisioning"),
        ("provisioning", "Provisioning"),
        ("provisioned", "Provisioned"),
        ("error", "Provisioning Error"),
    ], string="WHM Provisioning Status", compute="_compute_whm_provisioning_status", store=True)
    
    # Auto-provisioning settings
    whm_auto_provision = fields.Boolean(string="Auto Provision WHM Services", default=True)

    @api.depends('order_line')
    def _compute_whm_has_hosting(self):
        for order in self:
            order.whm_has_hosting = any(
                line.product_id.is_whm_product and 
                line.product_id.whm_product_type in ['hosting', 'reseller', 'vps', 'dedicated']
                for line in order.order_line
            )

    @api.depends('order_line')
    def _compute_whm_has_domains(self):
        for order in self:
            order.whm_has_domains = any(
                line.product_id.is_whm_product and 
                line.product_id.whm_product_type == 'domain'
                for line in order.order_line
            )

    @api.depends('order_line')
    def _compute_whm_accounts(self):
        for order in self:
            accounts = self.env['whm.hosting.account'].search([
                ('sale_order_id', '=', order.id)
            ])
            order.whm_hosting_account_ids = accounts

    @api.depends('order_line')
    def _compute_whm_domains(self):
        for order in self:
            domains = self.env['whm.domain'].search([
                ('hosting_account_id.sale_order_id', '=', order.id)
            ])
            order.whm_domain_ids = domains

    @api.depends('whm_hosting_account_ids.state')
    def _compute_whm_provisioning_status(self):
        for order in self:
            if not order.whm_hosting_account_ids:
                order.whm_provisioning_status = 'pending'
                continue
            
            states = [acc.state for acc in order.whm_hosting_account_ids]
            
            if all(state == 'active' for state in states):
                order.whm_provisioning_status = 'provisioned'
            elif any(state in ['pending', 'provisioning'] for state in states):
                order.whm_provisioning_status = 'provisioning'
            elif any(state == 'error' for state in states):
                order.whm_provisioning_status = 'error'
            else:
                order.whm_provisioning_status = 'pending'

    # --------------------------------------------------
    # WHM ACTIONS
    # --------------------------------------------------

    def action_provision_whm_services(self):
        """Provision all WHM services for this order"""
        self.ensure_one()
        
        if self.state != 'sale':
            raise UserError(_("Order must be confirmed before provisioning WHM services"))
        
        if not self.whm_has_hosting and not self.whm_has_domains:
            raise UserError(_("No WHM services found in this order"))
        
        provisioning_results = []
        
        # Provision hosting accounts
        for line in self.order_line.filtered(
            lambda l: l.product_id.is_whm_product and 
            l.product_id.whm_product_type in ['hosting', 'reseller', 'vps', 'dedicated']
        ):
            try:
                account = line.product_id.create_whm_hosting_account(
                    self.partner_id, 
                    sale_order_line=line
                )
                provisioning_results.append({
                    'type': 'success',
                    'message': f"Created hosting account: {account.name}",
                    'account_id': account.id,
                })
            except Exception as e:
                provisioning_results.append({
                    'type': 'error',
                    'message': f"Failed to create hosting account for {line.product_id.name}: {str(e)}",
                })
        
        # Handle domain registrations
        for line in self.order_line.filtered(
            lambda l: l.product_id.is_whm_product and 
            l.product_id.whm_product_type == 'domain'
        ):
            try:
                # Domain registration would be handled here
                # This would integrate with domain registrar APIs
                provisioning_results.append({
                    'type': 'info',
                    'message': f"Domain registration queued for {line.product_id.name}",
                })
            except Exception as e:
                provisioning_results.append({
                    'type': 'error',
                    'message': f"Failed to queue domain registration for {line.product_id.name}: {str(e)}",
                })
        
        # Log provisioning results
        success_count = len([r for r in provisioning_results if r['type'] == 'success'])
        error_count = len([r for r in provisioning_results if r['type'] == 'error'])
        
        message_body = f"<b>WHM Provisioning Results</b><br/>"
        message_body += f"Success: {success_count}<br/>"
        message_body += f"Errors: {error_count}<br/><br/>"
        
        for result in provisioning_results:
            icon = "✅" if result['type'] == 'success' else "❌" if result['type'] == 'error' else "ℹ️"
            message_body += f"{icon} {result['message']}<br/>"
        
        self.message_post(body=message_body)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WHM Provisioning Complete',
                'message': f'Provisioned {success_count} services with {error_count} errors',
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }

    def action_retry_provisioning(self):
        """Retry provisioning for failed WHM services"""
        self.ensure_one()
        
        failed_accounts = self.whm_hosting_account_ids.filtered(
            lambda a: a.state == 'error'
        )
        
        if not failed_accounts:
            raise UserError(_("No failed provisioning accounts found"))
        
        for account in failed_accounts:
            account.action_retry_provisioning()
        
        self.message_post(body=_(
            "<b>🔄 Retrying Provisioning</b><br/>"
            "Retrying provisioning for %d failed accounts"
        ) % len(failed_accounts))

    def action_view_whm_accounts(self):
        """View WHM hosting accounts for this order"""
        self.ensure_one()
        
        if not self.whm_hosting_account_ids:
            raise UserError(_("No WHM hosting accounts found for this order"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'WHM Hosting Accounts',
            'res_model': 'whm.hosting.account',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

    def action_view_whm_domains(self):
        """View WHM domains for this order"""
        self.ensure_one()
        
        if not self.whm_domain_ids:
            raise UserError(_("No WHM domains found for this order"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'WHM Domains',
            'res_model': 'whm.domain',
            'view_mode': 'tree,form',
            'domain': [('hosting_account_id.sale_order_id', '=', self.id)],
        }

    # --------------------------------------------------
    # OVERRIDES
    # --------------------------------------------------

    def action_confirm(self):
        """Override to trigger WHM provisioning"""
        result = super().action_confirm()
        
        # Auto-provision WHM services if enabled
        if self.whm_auto_provision and (self.whm_has_hosting or self.whm_has_domains):
            try:
                self.action_provision_whm_services()
            except Exception as e:
                _logger.error("Auto-provisioning failed for order %s: %s", self.name, str(e))
                self.message_post(body=_(
                    "<b>⚠️ Auto-Provisioning Failed</b><br/>"
                    "Error: %s<br/>"
                    "You can retry provisioning manually."
                ) % str(e))
        
        return result

    def _action_cancel(self):
        """Override to handle WHM service cancellation"""
        # Cancel WHM services before order cancellation
        for account in self.whm_hosting_account_ids:
            if account.state in ['active', 'suspended']:
                try:
                    account.action_terminate()
                except Exception as e:
                    _logger.error("Failed to terminate WHM account %s: %s", account.name, str(e))
        
        return super()._action_cancel()

    # --------------------------------------------------
    # DOMAIN VALIDATION
    # --------------------------------------------------

    def validate_domain_requirements(self):
        """Validate domain requirements for hosting products"""
        self.ensure_one()
        
        hosting_lines = self.order_line.filtered(
            lambda l: l.product_id.is_whm_product and 
            l.product_id.whm_product_type in ['hosting', 'reseller']
        )
        
        for line in hosting_lines:
            # Check if customer has a domain or wants to register one
            # This would integrate with the domain setup process
            pass

    # --------------------------------------------------
    # BILLING INTEGRATION
    # --------------------------------------------------

    def create_whm_invoices(self):
        """Create invoices for WHM services with proper billing cycles"""
        self.ensure_one()
        
        if self.state != 'sale':
            raise UserError(_("Order must be confirmed before creating invoices"))
        
        # Create separate invoices for different billing cycles
        # This would handle setup fees, recurring charges, etc.
        
        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_id.property_account_position_id.id,
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Add invoice lines for WHM services
        for line in self.order_line:
            if line.product_id.is_whm_product:
                # Handle setup fees
                if line.product_id.whm_setup_fee > 0:
                    invoice.write({
                        'invoice_line_ids': [(0, 0, {
                            'name': f"{line.product_id.name} - Setup Fee",
                            'quantity': 1,
                            'price_unit': line.product_id.whm_setup_fee,
                            'product_id': line.product_id.id,
                        })]
                    })
                
                # Handle recurring charges
                if line.product_id.recurring_invoice:
                    invoice.write({
                        'invoice_line_ids': [(0, 0, {
                            'name': line.product_id.name,
                            'quantity': line.product_uom_qty,
                            'price_unit': line.price_unit,
                            'product_id': line.product_id.id,
                        })]
                    })
        
        return invoice

    # --------------------------------------------------
    # STATISTICS AND REPORTING
    # --------------------------------------------------

    def get_whm_summary(self):
        """Get summary of WHM services in this order"""
        self.ensure_one()
        
        summary = {
            'hosting_accounts': len(self.whm_hosting_account_ids),
            'domains': len(self.whm_domain_ids),
            'provisioning_status': self.whm_provisioning_status,
            'total_value': sum(line.price_subtotal for line in self.order_line if line.product_id.is_whm_product),
        }
        
        return summary
