# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Initialize WHM hosting module after installation"""
    _logger.info("Initializing WHM Hosting Management module")
    
    # Create default system parameters if they don't exist
    env = registry['test.cr'] if hasattr(registry, 'test.cr') else None
    if env:
        try:
            # Set default WHM configuration parameters
            default_params = {
                'whm.api.verify_ssl': 'True',
                'whm.default_billing_cycle': 'monthly',
                'whm.auto_provision': 'True',
                'whm.enable_notifications': 'True',
                'whm.default_trial_days': '0',
                'whm.cancellation_notice_days': '30',
                'whm.usage_sync_interval': '1',
                'whm.enable_auto_suspend': 'False',
                'whm.enable_auto_renewal': 'True',
            }
            
            for key, value in default_params.items():
                existing = env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
                if not existing:
                    env['ir.config_parameter'].sudo().create({
                        'key': key,
                        'value': value,
                    })
                    _logger.info("Created default parameter: %s = %s", key, value)
            
            # Create default WHM groups if they don't exist
            group_model = env['res.groups']
            
            # WHM Customer group
            customer_group = env.ref('whm_hosting.group_whm_customer', raise_if_not_found=False)
            if not customer_group:
                customer_group = group_model.create({
                    'name': 'WHM Customer',
                    'comment': 'Can access own WHM services through portal',
                    'category_id': env.ref('base.module_category_website').id,
                })
                _logger.info("Created WHM Customer group")
            
            # WHM Operator group
            operator_group = env.ref('whm_hosting.group_whm_operator', raise_if_not_found=False)
            if not operator_group:
                operator_group = group_model.create({
                    'name': 'WHM Operator',
                    'comment': 'Can manage WHM accounts and basic operations',
                    'category_id': env.ref('base.module_category_operations').id,
                    'implied_ids': [(6, 0, [customer_group.id])],
                })
                _logger.info("Created WHM Operator group")
            
            # WHM Manager group
            manager_group = env.ref('whm_hosting.group_whm_manager', raise_if_not_found=False)
            if not manager_group:
                manager_group = group_model.create({
                    'name': 'WHM Manager',
                    'comment': 'Full access to WHM management features',
                    'category_id': env.ref('base.module_category_management').id,
                    'implied_ids': [(6, 0, [operator_group.id])],
                })
                _logger.info("Created WHM Manager group")
            
            # WHM Administrator group
            admin_group = env.ref('whm_hosting.group_whm_admin', raise_if_not_found=False)
            if not admin_group:
                admin_group = group_model.create({
                    'name': 'WHM Administrator',
                    'comment': 'Full administrative access to WHM system',
                    'category_id': env.ref('base.module_category_administration').id,
                    'implied_ids': [(6, 0, [manager_group.id])],
                    'users': [(6, 0, [env.ref('base.user_root').id])],
                })
                _logger.info("Created WHM Administrator group")
            
            # Create default WHM product categories
            product_category = env['product.category']
            
            hosting_category = product_category.search([('name', '=', 'WHM Hosting')], limit=1)
            if not hosting_category:
                hosting_category = product_category.create({
                    'name': 'WHM Hosting',
                    'parent_id': env.ref('product.product_category_all').id,
                })
                _logger.info("Created WHM Hosting product category")
            
            domain_category = product_category.search([('name', '=', 'Domain Registration')], limit=1)
            if not domain_category:
                domain_category = product_category.create({
                    'name': 'Domain Registration',
                    'parent_id': env.ref('product.product_category_all').id,
                })
                _logger.info("Created Domain Registration product category")
            
            ssl_category = product_category.search([('name', '=', 'SSL Certificates')], limit=1)
            if not ssl_category:
                ssl_category = product_category.create({
                    'name': 'SSL Certificates',
                    'parent_id': env.ref('product.product_category_all').id,
                })
                _logger.info("Created SSL Certificates product category")
            
            _logger.info("WHM Hosting Management module initialized successfully")
            
        except Exception as e:
            _logger.error("Failed to initialize WHM Hosting module: %s", str(e))
            raise


def uninstall_hook(cr, registry):
    """Clean up WHM hosting module data during uninstallation"""
    _logger.info("Uninstalling WHM Hosting Management module")
    
    env = registry['test.cr'] if hasattr(registry, 'test.cr') else None
    if env:
        try:
            # Remove WHM system parameters
            whm_params = env['ir.config_parameter'].sudo().search([
                ('key', 'like', 'whm.%')
            ])
            if whm_params:
                whm_params.unlink()
                _logger.info("Removed %d WHM system parameters", len(whm_params))
            
            # Note: We don't remove groups, products, or other data as they might be used by other modules
            _logger.info("WHM Hosting Management module uninstalled successfully")
            
        except Exception as e:
            _logger.error("Failed to cleanup WHM Hosting module: %s", str(e))
            raise
