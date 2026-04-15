# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request, content_disposition

_logger = logging.getLogger(__name__)


class WHMMainController(http.Controller):
    """Main WHM controller for public and customer-facing functionality"""

    @http.route('/whm/check_domain', type='json', auth='public', website=True)
    def check_domain_availability(self, **kwargs):
        """Check domain availability via WHOIS lookup"""
        domain = kwargs.get('domain', '').strip().lower()
        
        if not domain:
            return {
                'error': True,
                'message': 'Domain name is required'
            }
        
        # Basic domain validation
        import re
        if not re.match(r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z]{2,})+$', domain):
            return {
                'error': True,
                'message': 'Invalid domain format'
            }
        
        try:
            # This would integrate with a domain availability API
            # For now, simulate basic availability check
            tld = domain.split('.')[-1]
            common_tlds = ['com', 'net', 'org', 'co.za', 'co.uk']
            
            # Simulate some domains as taken
            taken_domains = ['google.com', 'facebook.com', 'microsoft.com']
            
            if domain in taken_domains:
                return {
                    'available': False,
                    'message': f'{domain} is already registered',
                    'domain': domain
                }
            else:
                return {
                    'available': True,
                    'message': f'{domain} is available for registration',
                    'domain': domain,
                    'tld': tld,
                    'pricing': self._get_domain_pricing(tld)
                }
                
        except Exception as e:
            _logger.error("Domain check failed for %s: %s", domain, str(e))
            return {
                'error': True,
                'message': 'Unable to check domain availability'
            }

    def _get_domain_pricing(self, tld):
        """Get pricing for specific TLD"""
        # This would fetch from WHM TLD configuration
        pricing = {
            'com': {'registration': 15.99, 'transfer': 15.99, 'renewal': 15.99},
            'net': {'registration': 16.99, 'transfer': 16.99, 'renewal': 16.99},
            'org': {'registration': 17.99, 'transfer': 17.99, 'renewal': 17.99},
            'co.za': {'registration': 8.99, 'transfer': 8.99, 'renewal': 8.99},
            'co.uk': {'registration': 12.99, 'transfer': 12.99, 'renewal': 12.99},
        }
        return pricing.get(tld, {'registration': 19.99, 'transfer': 19.99, 'renewal': 19.99})

    @http.route('/whm/packages', type='json', auth='public', website=True)
    def get_hosting_packages(self, **kwargs):
        """Get available hosting packages"""
        try:
            packages = request.env['whm.package'].search([
                ('is_active', '=', True)
            ])
            
            package_list = []
            for pkg in packages:
                package_list.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'description': pkg.description,
                    'disk_quota': pkg.disk_quota,
                    'bandwidth_limit': pkg.bandwidth_limit,
                    'max_addon_domains': pkg.max_addon_domains,
                    'max_email_accounts': pkg.max_email_accounts,
                    'max_databases': pkg.max_databases,
                    'monthly_price': pkg.monthly_price,
                    'annual_price': pkg.annual_price,
                    'is_featured': pkg.is_featured,
                    'resource_summary': pkg.get_resource_summary(),
                })
            
            return {
                'success': True,
                'packages': package_list
            }
            
        except Exception as e:
            _logger.error("Failed to get hosting packages: %s", str(e))
            return {
                'success': False,
                'message': 'Unable to load hosting packages'
            }

    @http.route('/whm/servers/status', type='json', auth='public', website=True)
    def get_server_status(self, **kwargs):
        """Get status of WHM servers (public info only)"""
        try:
            servers = request.env['whm.server'].search([
                ('is_active', '=', True)
            ])
            
            server_list = []
            for server in servers:
                server_list.append({
                    'name': server.name,
                    'hostname': server.hostname,
                    'status': server.status,
                    'current_accounts': server.current_accounts,
                    'max_accounts': server.max_accounts,
                })
            
            return {
                'success': True,
                'servers': server_list
            }
            
        except Exception as e:
            _logger.error("Failed to get server status: %s", str(e))
            return {
                'success': False,
                'message': 'Unable to load server status'
            }

    @http.route('/whm/tlds', type='json', auth='public', website=True)
    def get_available_tlds(self, **kwargs):
        """Get available TLDs for domain registration"""
        try:
            tlds = request.env['whm.tld'].search([
                ('is_active', '=', True)
            ])
            
            tld_list = []
            for tld in tlds:
                tld_list.append({
                    'name': tld.name,
                    'description': tld.description,
                    'registration_price': tld.registration_price,
                    'transfer_price': tld.transfer_price,
                    'renewal_price': tld.renewal_price,
                    'is_featured': tld.is_featured,
                    'is_restricted': tld.is_restricted,
                    'min_years': tld.min_years,
                    'max_years': tld.max_years,
                })
            
            return {
                'success': True,
                'tlds': tld_list
            }
            
        except Exception as e:
            _logger.error("Failed to get TLDs: %s", str(e))
            return {
                'success': False,
                'message': 'Unable to load available TLDs'
            }

    @http.route('/whm/calculator', type='json', auth='public', website=True)
    def calculate_hosting_cost(self, **kwargs):
        """Calculate hosting cost based on package and billing cycle"""
        package_id = kwargs.get('package_id')
        billing_cycle = kwargs.get('billing_cycle', 'monthly')
        years = kwargs.get('years', 1)
        
        if not package_id:
            return {
                'error': True,
                'message': 'Package ID is required'
            }
        
        try:
            package = request.env['whm.package'].browse(int(package_id))
            if not package.exists():
                return {
                    'error': True,
                    'message': 'Package not found'
                }
            
            price = package.get_price_for_cycle(billing_cycle)
            setup_fee = package.setup_fee
            
            # Calculate total cost
            if billing_cycle in ['annually', 'biennially', 'triennially']:
                multiplier = {'annually': 1, 'biennially': 2, 'triennially': 3}.get(billing_cycle, 1)
                total = (price * multiplier) + setup_fee
            else:
                total = price + setup_fee
            
            return {
                'success': True,
                'price': price,
                'setup_fee': setup_fee,
                'total': total,
                'billing_cycle': billing_cycle,
                'currency': 'USD'  # This should be configurable
            }
            
        except Exception as e:
            _logger.error("Cost calculation failed: %s", str(e))
            return {
                'error': True,
                'message': 'Unable to calculate cost'
            }

    @http.route('/whm/validate_password', type='json', auth='public', website=True)
    def validate_whm_password(self, **kwargs):
        """Validate password strength for WHM requirements"""
        password = kwargs.get('password', '')
        
        if not password:
            return {
                'valid': False,
                'strength': 0,
                'message': 'Password is required'
            }
        
        # WHM password requirements
        score = 0
        messages = []
        
        if len(password) < 10:
            messages.append("Password must be at least 10 characters")
        else:
            score += 1
        
        if not any(c.isupper() for c in password):
            messages.append("Password must contain uppercase letters")
        else:
            score += 1
        
        if not any(c.islower() for c in password):
            messages.append("Password must contain lowercase letters")
        else:
            score += 1
        
        if not any(c.isdigit() for c in password):
            messages.append("Password must contain numbers")
        else:
            score += 1
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            messages.append("Password must contain special characters")
        else:
            score += 1
        
        strength_levels = {
            0: "Very Weak",
            1: "Weak",
            2: "Fair",
            3: "Good",
            4: "Strong",
            5: "Very Strong"
        }
        
        return {
            'valid': score >= 3,
            'strength': score,
            'strength_text': strength_levels.get(score, "Unknown"),
            'message': ' '.join(messages) if messages else "Password meets WHM requirements"
        }

    @http.route('/whm/contact', type='http', auth='public', website=True, methods=['POST'])
    def submit_contact_form(self, **kwargs):
        """Handle WHM contact form submissions"""
        try:
            name = kwargs.get('name', '').strip()
            email = kwargs.get('email', '').strip()
            subject = kwargs.get('subject', '').strip()
            message = kwargs.get('message', '').strip()
            
            if not all([name, email, subject, message]):
                return request.render('website_http_error.http_error', {
                    'error_message': 'All fields are required'
                })
            
            # Create lead or send email
            lead_vals = {
                'name': f"WHM Contact: {subject}",
                'partner_name': name,
                'email_from': email,
                'description': message,
                'team_id': request.env.ref('sales_team.crm_team_sales').id,
            }
            
            request.env['crm.lead'].sudo().create(lead_vals)
            
            return request.render('website.contactus_thanks', {
                'thankyou_message': 'Thank you for contacting us. We will get back to you soon!'
            })
            
        except Exception as e:
            _logger.error("Contact form submission failed: %s", str(e))
            return request.render('website_http_error.http_error', {
                'error_message': 'Unable to submit contact form'
            })
