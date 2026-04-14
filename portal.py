# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class WHMPortalController(CustomerPortal):
    """WHM Customer Portal Controller"""

    def _prepare_home_portal_values(self, counters):
        """Add WHM counters to portal home"""
        values = super()._prepare_home_portal_values(counters)
        
        if request.env.user.partner_id:
            partner = request.env.user.partner_id
            
            # Count WHM services
            values['whm_account_count'] = len(partner.whm_hosting_account_ids)
            values['whm_active_account_count'] = len(
                partner.whm_hosting_account_ids.filtered(lambda a: a.state == 'active')
            )
            values['whm_domain_count'] = len(partner.whm_domain_ids)
        
        return values

    # --------------------------------------------------
    # HOSTING ACCOUNTS PORTAL
    # --------------------------------------------------

    @http.route(['/my/hosting', '/my/hosting/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_hosting_accounts(self, page=1, **kwargs):
        """Customer hosting accounts portal page"""
        partner = request.env.user.partner_id
        
        # Get hosting accounts
        accounts = partner.whm_hosting_account_ids
        
        # Pagination
        pager = portal_pager(
            url="/my/hosting",
            total=len(accounts),
            page=page,
            step=10
        )
        
        # Get accounts for current page
        offset = pager['offset']
        accounts_page = accounts[offset:offset + pager['step']]
        
        values = {
            'page_name': 'hosting',
            'accounts': accounts_page,
            'pager': pager,
            'default_url': '/my/hosting',
        }
        
        return request.render("whm_hosting.portal_my_hosting_accounts", values)

    @http.route(['/my/hosting/<int:account_id>'], type='http', auth='user', website=True)
    def portal_hosting_account(self, account_id, **kwargs):
        """Individual hosting account details"""
        partner = request.env.user.partner_id
        
        account = request.env['whm.hosting.account'].search([
            ('id', '=', account_id),
            ('partner_id', '=', partner.id)
        ])
        
        if not account:
            return request.redirect('/my/hosting')
        
        # Get account domains
        domains = account.domain_ids
        
        values = {
            'page_name': 'hosting',
            'account': account,
            'domains': domains,
        }
        
        return request.render("whm_hosting.portal_hosting_account", values)

    @http.route(['/my/hosting/<int:account_id>/login'], type='http', auth='user', website=True)
    def portal_cpanel_login(self, account_id, **kwargs):
        """Generate auto-login URL for cPanel"""
        partner = request.env.user.partner_id
        
        account = request.env['whm.hosting.account'].search([
            ('id', '=', account_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'active')
        ])
        
        if not account:
            return request.redirect('/my/hosting')
        
        try:
            login_url = account.get_cpanel_autologin_url()
            return request.redirect(login_url)
        except Exception as e:
            _logger.error("cPanel auto-login failed for account %s: %s", account_id, str(e))
            values = {
                'page_name': 'hosting',
                'error': 'Unable to generate cPanel login URL. Please contact support.',
                'account': account,
            }
            return request.render("whm_hosting.portal_hosting_account", values)

    # --------------------------------------------------
    # DOMAIN MANAGEMENT PORTAL
    # --------------------------------------------------

    @http.route(['/my/domains', '/my/domains/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_domains(self, page=1, **kwargs):
        """Customer domains portal page"""
        partner = request.env.user.partner_id
        
        # Get all domains
        domains = partner.whm_domain_ids
        
        # Pagination
        pager = portal_pager(
            url="/my/domains",
            total=len(domains),
            page=page,
            step=10
        )
        
        # Get domains for current page
        offset = pager['offset']
        domains_page = domains[offset:offset + pager['step']]
        
        values = {
            'page_name': 'domains',
            'domains': domains_page,
            'pager': pager,
            'default_url': '/my/domains',
        }
        
        return request.render("whm_hosting.portal_my_domains", values)

    @http.route(['/my/domains/<int:domain_id>'], type='http', auth='user', website=True)
    def portal_domain_details(self, domain_id, **kwargs):
        """Individual domain details"""
        partner = request.env.user.partner_id
        
        domain = request.env['whm.domain'].search([
            ('id', '=', domain_id),
            ('hosting_account_id.partner_id', '=', partner.id)
        ])
        
        if not domain:
            return request.redirect('/my/domains')
        
        values = {
            'page_name': 'domains',
            'domain': domain,
            'account': domain.hosting_account_id,
        }
        
        return request.render("whm_hosting.portal_domain_details", values)

    # --------------------------------------------------
    # HOSTING SETUP WIZARD
    # --------------------------------------------------

    @http.route(['/my/hosting/setup/<int:order_id>'], type='http', auth='user', website=True)
    def portal_hosting_setup(self, order_id, **kwargs):
        """Hosting setup wizard for new orders"""
        partner = request.env.user.partner_id
        
        # Get the sale order
        order = request.env['sale.order'].search([
            ('id', '=', order_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'sale')
        ])
        
        if not order:
            return request.redirect('/my')
        
        # Check if order has WHM hosting products
        if not order.whm_has_hosting:
            return request.redirect('/my')
        
        # Get hosting account for this order
        hosting_account = request.env['whm.hosting.account'].search([
            ('sale_order_id', '=', order_id),
            ('partner_id', '=', partner.id)
        ], limit=1)
        
        if not hosting_account:
            # Create hosting account if it doesn't exist
            hosting_lines = order.order_line.filtered(
                lambda l: l.product_id.is_whm_product and 
                l.product_id.whm_product_type in ['hosting', 'reseller']
            )
            if hosting_lines:
                hosting_account = hosting_lines[0].product_id.create_whm_hosting_account(
                    partner, hosting_lines[0]
                )
        
        values = {
            'page_name': 'hosting_setup',
            'order': order,
            'hosting_account': hosting_account,
            'error': kwargs.get('error'),
        }
        
        return request.render("whm_hosting.portal_hosting_setup", values)

    @http.route(['/my/hosting/setup/<int:order_id>/submit'], type='http', auth='user', website=True, methods=['POST'])
    def portal_hosting_setup_submit(self, order_id, **kwargs):
        """Process hosting setup form submission"""
        partner = request.env.user.partner_id
        
        order = request.env['sale.order'].search([
            ('id', '=', order_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'sale')
        ])
        
        if not order:
            return request.redirect('/my')
        
        try:
            # Get form data
            domain = kwargs.get('domain', '').strip()
            password = kwargs.get('password', '')
            confirm_password = kwargs.get('confirm', '')
            
            # Validate inputs
            if password != confirm_password:
                return request.redirect(f'/my/hosting/setup/{order_id}?error=Passwords do not match')
            
            # Get hosting account
            hosting_account = request.env['whm.hosting.account'].search([
                ('sale_order_id', '=', order_id),
                ('partner_id', '=', partner.id)
            ], limit=1)
            
            if not hosting_account:
                return request.redirect(f'/my/hosting/setup/{order_id}?error=Hosting account not found')
            
            # Update hosting account with form data
            hosting_account.write({
                'cpanel_domain': domain if domain else False,
                'cpanel_password': password if password else False,
            })
            
            # Provision the account
            hosting_account.action_provision()
            
            return request.redirect(f'/my/hosting/{hosting_account.id}')
            
        except Exception as e:
            _logger.error("Hosting setup failed for order %s: %s", order_id, str(e))
            return request.redirect(f'/my/hosting/setup/{order_id}?error={str(e)}')

    # --------------------------------------------------
    # BILLING PORTAL
    # --------------------------------------------------

    @http.route(['/my/billing/whm'], type='http', auth='user', website=True)
    def portal_whm_billing(self, **kwargs):
        """WHM billing information portal"""
        partner = request.env.user.partner_id
        
        # Get billing summary
        billing_summary = partner.get_whm_billing_summary()
        
        # Get recent invoices related to WHM services
        invoices = request.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['posted', 'sent']),
            ('invoice_line_ids.product_id.is_whm_product', '=', True),
        ], order='invoice_date desc', limit=10)
        
        values = {
            'page_name': 'billing',
            'billing_summary': billing_summary,
            'invoices': invoices,
        }
        
        return request.render("whm_hosting.portal_whm_billing", values)

    # --------------------------------------------------
    # SUPPORT PORTAL
    # --------------------------------------------------

    @http.route(['/my/support/whm'], type='http', auth='user', website=True)
    def portal_whm_support(self, **kwargs):
        """WHM support tickets portal"""
        partner = request.env.user.partner_id
        
        # Get helpdesk tickets related to WHM services
        tickets = request.env['helpdesk.ticket'].search([
            ('partner_id', '=', partner.id),
            ('ticket_type', '=', 'whm'),
        ], order='create_date desc', limit=10)
        
        values = {
            'page_name': 'support',
            'tickets': tickets,
        }
        
        return request.render("whm_hosting.portal_whm_support", values)

    @http.route(['/my/support/whm/create'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_whm_support_create(self, **kwargs):
        """Create WHM support ticket"""
        partner = request.env.user.partner_id
        
        if request.httprequest.method == 'POST':
            try:
                # Get form data
                subject = kwargs.get('subject', '').strip()
                description = kwargs.get('description', '').strip()
                account_id = kwargs.get('account_id')
                domain_id = kwargs.get('domain_id')
                
                if not subject or not description:
                    values = {
                        'page_name': 'support',
                        'error': 'Subject and description are required',
                        'accounts': partner.whm_hosting_account_ids,
                        'domains': partner.whm_domain_ids,
                    }
                    return request.render("whm_hosting.portal_whm_support_create", values)
                
                # Create helpdesk ticket
                ticket_vals = {
                    'name': subject,
                    'description': description,
                    'partner_id': partner.id,
                    'ticket_type': 'whm',
                }
                
                if account_id:
                    ticket_vals['whm_account_id'] = int(account_id)
                
                if domain_id:
                    ticket_vals['whm_domain_id'] = int(domain_id)
                
                request.env['helpdesk.ticket'].create(ticket_vals)
                
                return request.redirect('/my/support/whm')
                
            except Exception as e:
                _logger.error("Failed to create WHM support ticket: %s", str(e))
                values = {
                    'page_name': 'support',
                    'error': 'Failed to create support ticket',
                    'accounts': partner.whm_hosting_account_ids,
                    'domains': partner.whm_domain_ids,
                }
                return request.render("whm_hosting.portal_whm_support_create", values)
        
        # GET request - show form
        values = {
            'page_name': 'support',
            'accounts': partner.whm_hosting_account_ids,
            'domains': partner.whm_domain_ids,
        }
        
        return request.render("whm_hosting.portal_whm_support_create", values)
