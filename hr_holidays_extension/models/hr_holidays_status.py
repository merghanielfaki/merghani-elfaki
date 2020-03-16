'''
Created on Aug 13, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _

class HolidaysType(models.Model):

    _inherit = "hr.leave.type"   #"hr.holiday.status"
    _order = 'name'
    
    is_gender = fields.Boolean('Gender')
    is_religion = fields.Boolean('Religion')
    gender = fields.Selection([('m', 'Male'), ('f', 'Female')], 'Gender')
    religion = fields.Selection([('m', 'Muslim'), ('o', 'Other')], 'Religion')
    ex_rest_days = fields.Boolean('Exclude Rest Days',
                                       help="If enabled, the employee's day off is skipped in leave days calculation.")
    ex_public_holidays = fields.Boolean('Exclude Public Holidays',
                                             help="If enabled, public holidays are skipped in leave days calculation.")
    min_days = fields.Integer('Minimum Days', digits=(16, 1),
                                 help="Minimum number of days the employee should at least attend so it won't count the rest days.")
    max_days = fields.Integer('Maximum Days', digits=(16, 1),
                                 help="Maximum number of days the employee can request for this leave type (Note, it will ignore the leave allocation and allow to override limit cases for this type.).")
    attachment_mandatory = fields.Boolean('Attachment is mandatory')
    alternative_emp_mandatory = fields.Boolean('Alternative employee is mandatory')
    ceo_number = fields.Integer('CEO day limit')
    #manager_appr = fields.Boolean('Manager Approval')
    hr_appr = fields.Boolean('Direct to HR Approval')
    #ceo_appr = fields.Boolean('CEO Approval')
    vp_appr = fields.Boolean('VP Approval')    
    allow_trial_period = fields.Boolean('Trial Period Exception', 
                                        help='Allow the employees to apply for this leave type even if he/she in the trial period.')
    
    code = fields.Char('Code', size=16, required=True)
    ignore_locked_period = fields.Boolean('Ignore Locked Period', help='Allow the employees to apply for this leave type even if the leave period within a locked payroll period.')
    allow_future_balance = fields.Boolean("Allow Future Balance", help="Allow the calculation of future leave for this type.")
    partial_leave =  fields.Boolean('Partial Day Leave')
    
   #@api.multi
    def name_get(self):
        if not self._context.get('employee_id'):
            # leave counts is based on employee_id, would be inaccurate if not based on correct employee
            return super(HolidaysType, self).name_get()
        res = []
        for record in self:
            name = record.name
            if not record.limit:
                name = "%(name)s (%(count)s)" % {
                    'name': name,
                    'count': _('%g') % (record.remaining_leaves or 0.0)
                }
            res.append((record.id, name))
        return res
