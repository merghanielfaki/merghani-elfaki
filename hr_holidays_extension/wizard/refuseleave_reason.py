'''
Created on Aug 20, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from odoo.exceptions import Warning

class RrefuseLeaveReason(models.TransientModel):
    _name = 'refuseleave.reason'
    
    reason = fields.Text('Description', required=True)
    
  #  @api.multi
    def refuseaction(self):
        self.ensure_one()
        active_id = self._context.get('active_id')
        leave = self.env['hr.leave'].browse(active_id)
        if leave.employee_id.user_id == self.env.user and not self.env.user.has_group('base_extension.group_ceo'):
            raise Warning(_('You cannot refuse your own request'))
        leave.refuse_reason = self.reason
        leave.action_refuse()
        leave._send_mail('email_template_holidays_update_emp2')
        return {'type': 'ir.actions.act_window_close'}
