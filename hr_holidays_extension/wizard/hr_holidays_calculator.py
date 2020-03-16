'''
Created on Aug 23, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from odoo.addons.custom.hijri import getGregorian, getHijri
from odoo.exceptions import ValidationError, Warning
from dateutil.relativedelta import relativedelta
from odoo.addons.custom.util import relativeDelta, relativeDate

class HolidaysCalculator (models.TransientModel):
    _name = 'hr.holidays.calculator'
    _description = "Holidays Calculator"
    
    @api.model
    def _get_date_to(self):        
        return '%s-12-31' % fields.Date.today()[:4]
    
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, default = lambda self : self.env.user.employee_ids[:1])
    allocate_balance = fields.Boolean('Allocate Balance?')
    holiday_status_id = fields.Many2one("hr.leave.type", "Leave Type")
    previous_leaves_ids = fields.Many2many('hr.leave', string='Taken Leaves', compute='_calc_leaves' )
    allocated_leaves_ids = fields.Many2many('hr.leave', string='Allocated Leaves', compute='_calc_leaves')
    
    date_from = fields.Date('Start Date')
    hijri_date_from = fields.Char('Start Hijri Date')
    date_to = fields.Date('End Date', default = _get_date_to)
    hijri_date_to = fields.Char('End Hijri Date')
    #### Leave Details #####
    taken_leave_balance = fields.Float('Taken Leaves', compute='_calc_leaves', help='Total number of the approved leave requests.')
    allocated_leave_balance = fields.Float('Allocated Leaves', compute='_calc_leaves', help='Total number of the allocated approved leave balance.')
    deserved_balance = fields.Float('Deserved Balance', help='The total number of leave balance this employee deserve within the selected period.')
    ###
    leave_max_days = fields.Float('Max Annual Leave Days', help='The maximum leave balance to be allocated for this employee based on the HR policy.')
    warning_message = fields.Text('Warning', compute = '_calc_warning_message')
    
    @api.depends('employee_id')
    def _calc_warning_message(self):
        for record in self:
            contract = self.env['hr.contract'].search([('employee_id','=', record.employee_id.id)], count= True)
            if contract:
                record.warning_message = False
            else:
                record.warning_message = "The selected employee doesn't have any contracts, Please create a contract for him/her" 
                
    @api.depends('employee_id','holiday_status_id')    
    def _calc_leaves(self):
        Holidays = self.env['hr.leave']
        validate = lambda record: record.state=='validate'
        for record in self:
            domain = [('employee_id','=', record.employee_id.id), ('state','not in', ['cancel','refuse'])]
            if record.holiday_status_id:
                domain.append(('holiday_status_id','=', record.holiday_status_id.id))
            taken = Holidays.search(domain + [('type','=', 'remove')])
            allocated = Holidays.search(domain + [('type','=', 'add')])
            record.previous_leaves_ids = taken
            record.allocated_leaves_ids = allocated
            record.taken_leave_balance = sum(taken.filtered(validate).mapped('number_of_days_temp'))
            record.allocated_leave_balance = sum(allocated.filtered(validate).mapped('number_of_days_temp'))
    
    @api.onchange('employee_id','allocate_balance')
    def set_date_from(self):
        self.date_from = self.employee_id.initial_employment_date
    
    @api.onchange('leave_max_days','date_from','date_to', 'allocate_balance')
    def set_deserved_balance(self):
        if self.leave_max_days and self.date_from and self.date_to and self.allocate_balance:
            delta = relativeDelta(relativeDate(self.date_to,days=1), self.date_from)                 
            years = delta.years + delta.months / 12.0 + delta.days / 365.0
            self.deserved_balance = round(self.leave_max_days * years,2)
    
    @api.onchange('date_from')
    def on_change_date_from(self):
        self.hijri_date_from = getHijri(self.date_from)
        
    @api.onchange('date_to')
    def on_change_date_to(self):
        self.hijri_date_to = getHijri(self.date_to)        
                
    @api.onchange('hijri_date_from')
    @api.constrains('hijri_date_from')
    def on_change_hijri_date_from(self):
        self.check_hijri('hijri_date_from')
        if isinstance(self[:1].id, models.NewId):
            self.date_from = getGregorian(self.hijri_date_from)   
            
    @api.onchange('hijri_date_to')
    @api.constrains('hijri_date_to')
    def on_change_hijri_date_to(self):
        self.check_hijri('hijri_date_to')
        if isinstance(self[:1].id, models.NewId):
            self.date_to = getGregorian(self.hijri_date_to)               
    
    @api.onchange('date_from','date_to') 
    @api.constrains('date_from','date_to')
    def check_date(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_('The start date must be anterior to the end date.'))
            
   # @api.multi
    def allocate_initial_leave_balance(self):
        if self.warning_message:
            raise Warning(self.warning_message)
        leave_allocation = {
                    'name': 'Auto Leave Allocation',
                    'type': 'add',
                    'employee_id': self.employee_id.id,
                    'number_of_days_temp': self.deserved_balance,
                    'holiday_status_id': self.holiday_status_id.id,
                }
        leave_id = self.env['hr.leave'].create(leave_allocation)
        leave_id.action_confirm()
                                
        
