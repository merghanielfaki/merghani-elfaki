'''
Created on Aug 13, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError, Warning, UserError, AccessError
from datetime import datetime, timedelta, date
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as OE_DTFORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
import math

import logging
from odoo.tools.float_utils import float_compare
_logger = logging.getLogger(__name__)

_states={'draft':[('readonly', False)], 'confirm':[('readonly', False)]}

HOURS_PER_DAY = 8

class Holidays(models.Model):
    _name = "hr.leave"
    _inherit = ["hr.leave",'approval.record']
    _order = 'date_from asc, type desc'
    
    _approval_config = 'hr.holidays.approval'    
    _approval_log = 'hr.holidays.logs'
    _approve_state='validate'
    _draft_state='draft'
    _reject_state='refuse'    
    
    @api.model
    def _get_state(self):
        return [('draft', 'To Submit')] \
            + self._approval_states() \
            + [('validate', 'Approved'),                                                            
                ('refuse', 'Refused'), 
                ('cancel', 'Cancelled'),
              ]                          
            
    state = fields.Selection(_get_state, default = 'draft')

    sla_state = fields.Selection([('green', 'Not Exceed SLA'),('yellow', 'SLA'),('red', 'Exceed SLA'),('gray', 'N/A')],
                compute = '_compute_sla_state',
                string = 'SLA State')
    state_icon = fields.Char(compute = '_compute_state_icon', store = False, string='SLA')                
    
    real_days_value = fields.Float('Total Leave', digits=(16, 1))
    real_days = fields.Float('Total Leave', related='real_days_value', readonly = True)
    real_hours_value = fields.Float('Total Hours Value', digits=(16, 2))
    real_hours = fields.Float('Total Hours', related='real_hours_value', readonly = True, digits=(16, 2))
    
    working_days_value = fields.Float('Working Days', digits=(16, 1))
    working_days = fields.Float('Working Days', related='working_days_value', readonly = True)
    
    rest_days_value = fields.Float('Rest Days', digits=(16, 1))
    rest_days = fields.Float('Rest Days', related='rest_days_value', readonly = True)
    type = fields.Selection([
            ('remove', 'Leave Request'),
            ('add', 'Allocation Request')
        ], string='Request Type', required=True, readonly=True, index=True, default='remove',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]},
        help="Choose 'Leave Request' if someone wants to take an off-day. "
             "\nChoose 'Allocation Request' if you want to increase the number of leaves available for someone")
    public_holiday_days_value = fields.Float('Public Holidays', digits=(16, 1))
    public_holiday_days = fields.Float('Public Holidays', related='public_holiday_days_value', readonly = True)
    
    total_days_value = fields.Float('Total Days', digits=(16, 1))
    total_days = fields.Float('Total Days', related='total_days_value', readonly = True)
    
    return_date_value = fields.Char('Return Date', size=32)
    return_date = fields.Char('Return Date', related='return_date_value', readonly = True)
    
    max_leaves_value = fields.Float('Actual Balance')
    max_leaves = fields.Float('Actual Balance', related='max_leaves_value', readonly = True)
    
    leaves_taken_value = fields.Integer('Leaves Already Taken Value')
    leaves_taken = fields.Integer('Leaves Already Taken', related='leaves_taken_value', readonly = True)
    
    remaining_leaves_value = fields.Float('Previous Remaining Leaves Value')
    remaining_leaves = fields.Float('Previous Remaining Leaves', related='remaining_leaves_value', readonly = True)
    
    curr_remaining_leaves_value = fields.Float('Current Remaining Leaves')
    curr_remaining_leaves = fields.Float('Current Remaining Leaves', related='curr_remaining_leaves_value', readonly = True)
    
    future_balance_value = fields.Float('Future Balance')
    future_balance = fields.Float('Future Balance', compute = '_calc_future_balance')
    
    max_allowed_days_value = fields.Float('Maximum Allowed Days')
    max_allowed_days = fields.Float('Maximum Allowed Days', related='max_allowed_days_value', readonly = True)    
    
    
    exit_reentry_visa = fields.Boolean('Exit Reentry visa')
    vacation_salary_advance = fields.Boolean('Vacation Salary advance')
    tickets_required = fields.Boolean('Tickets Required')
    tickets = fields.Integer('Number of Tickets')
    transportation_to_airport = fields.Boolean('Transportation to Airport')
    return_belonging = fields.Boolean('Return Belonging')
    actual_return_date = fields.Date('Actual Return Date')
    include_exclude_lines = fields.One2many('hr.holidays.days_include', 'request_id', 'Include Exlucded Lines')
    half_day =  fields.Boolean('Half Day', readonly=True, states=_states)
    partial_leave =  fields.Boolean('Partial Day Leave', states=_states)
    partial_leave_enabled = fields.Boolean(compute='_check_partail_enabled')
    flag_attachment = fields.Boolean('Flag Attachment')
    alternative_emp_id = fields.Many2one('hr.employee', 'Alternative Employee ')
    outside_ksa = fields.Boolean('Outside KSA')
    refuse_reason = fields.Text('Refuse Reason')
    flag_emp_mandatory = fields.Boolean('Flag employee is mandatory')
    nationality_id = fields.Many2one('res.country', related='employee_id.country_id', string='Nationality', readonly=True, store=True)
    empl_contract_id = fields.Many2one('hr.contract', related ='employee_id.contract_id', string='Contract', store=False)
    flag_saudi = fields.Boolean('Flag_saudi', compute = '_calc_flag_saudi', store = True)                
    ex_leave = fields.Boolean('Exception Leave')
    emp_id_view = fields.Many2one('hr.employee', 'Employee', related='employee_id', readonly = True, store = False)
    #fix repeated messages issue
    repeated_message = fields.Boolean('Repeated Message', invisible=True)
        
    payroll_period_state = fields.Selection([('unlocked', 'Unlocked'), ('locked', 'Locked')],
                                                 'Payroll Period State', compute='_calc_payroll_period_state', compute_sudo=True, store = False)
        
    delegation_id = fields.Many2one('delegation', ondelete='set null', copy = False)
    delegation_name = fields.Char(compute='_calc_delegation_count', store = False)
    
    delegation_ignored = fields.Boolean('I do not want to delegate', default = True, readonly = True, states={'draft' : [('readonly', False)]})
    
    department_id = fields.Many2one('hr.department', compute='_calc_department_id', compute_sudo=True, related=False, string='Department', readonly=True, store=True)
    
    state_id = fields.Many2one(_approval_config)

    approval_logs = fields.One2many('hr.holidays.logs', 'record_id', string='Status Logs',readonly=True)
    
    date_time_from = fields.Datetime('Start Hour', readonly=True, index=True, copy=False,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    date_time_to = fields.Datetime('End Hour', readonly=True, copy=False,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    leave_balance_char = fields.Char('My Balance', method=True, readonly=True, compute='_calc_my_balance')
    new_leave_balance_char = fields.Char('My New Balance', method=True, readonly=True, compute='_calc_my_new_balance')
    total_hours_char = fields.Char('Hours to Char', method=True, readonly=True, compute='_calc_taken_hours')
    
    number_of_days_temp = fields.Float('Allocation', digits=(16, 4))
    
    cancel_enabled = fields.Boolean(compute = '_calc_enabled')
    requster_cancel = fields.Boolean('Canceled by employee')

    _sql_constraints = [
        ('delegation_uk', 'unique(delegation_id)', 'Delegation should be unique'),
        ]                                     
                
    def _check_state_access_right(self, vals):
        return True
                    
    @api.constrains('date_from','date_to','employee_id')
    def _check_attendance(self):
        for record in self:
            if record.type=='remove' and not record.partial_leave:
                att = self.env['hr.attendance.punch'].sudo().search([('employee_id', '=', record.employee_id.id), 
                                                              ('name', '>=', record.date_from),
                                                              ('name', '<=', record.date_to)], count = True)
                if att:
                    raise  ValidationError(_('There is already one or more attendance records for the date you have chosen.'))
    
    ##@api.multi
    def _calc_enabled(self):
        for record in self:
            record.cancel_enabled = record.state == 'validate' and record.employee_id.user_id == self.env.user and record.date_from > fields.Date.today()
            
    
    @api.onchange('holiday_status_id')
    def _check_partail_enabled(self):
        for record in self:
            record.partial_leave_enabled = record.holiday_status_id.partial_leave and record.employee_id.company_id.id != 3
            record.partial_leave = False
            
    @api.onchange('partial_leave')
    def _onChange_partial_leave(self):
        for record in self:
            record.date_time_from = False
            record.date_time_to = False
            record.date_from = False
            record.date_to = False
    
    @api.depends('employee_id.department_id')
    def _calc_department_id(self):
        for record in self:
            if record.state == 'validate':
                record.department_id = record._read_db_value('department_id')
            else:
                record.department_id = record.employee_id.department_id
    
    ##@api.multi
    def _compute_can_reset(self):
        """ User can reset a leave request if it is its own leave request
            or if he is an Hr Manager.
        """        
        for holiday in self:
            holiday.can_reset = holiday.employee_id.user_id == self.env.user and (holiday.state == 'refuse' or holiday.state == 'cancel' )            
                
    @api.depends('employee_id')
    def _calc_payroll_period_state(self):
        if 'hr.payroll.period' not in self.env:
            return
        for record in self:                
            schedule_id=record.employee_id.sudo().contract_id.pps_id.id
            if schedule_id:
                period=self.env['hr.payroll.period'].sudo().search([('schedule_id','=', schedule_id), ('date_start','<=', self.date_to), ('date_end','>=', self.date_to)], limit = 1)
                record.payroll_period_state = period.state=='locked' and 'locked' or 'unlocked'
            else:
                record.payroll_period_state = 'unlocked'
    
    @api.depends('employee_id.country_id')
    def _calc_flag_saudi(self):
        sa = self.env.ref('base.sa')
        for record in self:
            record.flag_saudi = record.employee_id.country_id == sa
        
    @api.depends('future_balance_value','holiday_status_id.allow_future_balance')
    def _calc_future_balance(self):
        for record in self:
            record.future_balance = record.holiday_status_id.allow_future_balance and record.future_balance_value
                                                            
    #@api.multi
    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, 'Leave Request From: %s' % record.employee_id.name))
        return res
    
    @api.onchange('date_from')
    def _onchange_date_from(self):
        pass
    
    @api.onchange('date_to')
    def _onchange_date_to(self):
        pass
    
    @api.onchange('date_time_from', 'date_time_to')
    def _onchange_date_time(self):
        from_dt = fields.Datetime.from_string(self.date_time_from)
        to_dt = fields.Datetime.from_string(self.date_time_to)
        if self.date_time_from and not self.date_time_to or self.date_time_from > self.date_time_to:
            self.date_time_to = self.date_time_from
        if to_dt and from_dt and to_dt > from_dt:
            if from_dt.date() != to_dt.date():
                self.date_time_to = self.date_time_from
        if self.date_time_from and self.date_time_to:
            from_dt = fields.Datetime.from_string(self.date_time_from).replace(second=0, microsecond=0)
            to_dt = fields.Datetime.from_string(self.date_time_to).replace(second=0, microsecond=0)
            self.date_time_from = str(from_dt)
            self.date_time_to = str(to_dt)
        self.date_from = self.date_time_from
        self.date_to = self.date_time_to
        
    
    @api.onchange('date_from','date_to','employee_id','holiday_status_id','half_day','date_time_from','date_time_to')
    def _onchange_date(self):
        result = {'domain':{}}
        self.holiday_status_id.name_get()
        holiday_status_id_domain = []
        gender = self.employee_id.sudo().gender
        holiday_status_id_domain.append(['|', ('is_gender', '=', False), ('gender', '=', gender and gender[0])])
        holiday_status_id_domain.append(['|', ('is_religion', '=', False), ('religion', '=', self.employee_id.religion and self.employee_id.religion[0])])
        holiday_status_id_domain = expression.AND(holiday_status_id_domain)  
        result['domain']['holiday_status_id'] = holiday_status_id_domain            
        
        if self.holiday_status_id and self.holiday_status_id not in self.env['hr.leave.type'].search(holiday_status_id_domain):
            self.holiday_status_id = False                   
                   
        alt_emp_domain = ['&',('id','!=',self.employee_id.id),'|',('department_id','=',self.employee_id.department_id.id),'&',('parent_id','=',self.employee_id.id),('manager','=',True)]
        result['domain']['alternative_emp_id'] = alt_emp_domain
        if self.alternative_emp_id and self.alternative_emp_id not in self.env['hr.employee'].search(alt_emp_domain):
            self.alternative_emp_id = False
            
        if self.half_day and self.date_from and self.date_to != self.date_from:
            self.date_to = self.date_from
            
        if self.date_from and not self.date_to or self.date_from > self.date_to:
            self.date_to = self.date_from
        
        if not self.date_from or not self.date_to:            
            return result
            
        if self.date_from > self.date_to:
            raise ValidationError(_('The start date must be anterior to the end date.'))            
                               
        dt = fields.Datetime.from_string(self.date_from)
        dt_to = fields.Datetime.from_string(self.date_to)
       
        """
        Update the dates based on the number of days requested.
        """

        holiday_obj = self.env.get('hr.holidays.public')
        sched_tpl_obj = self.env.get('hr.schedule.template')
                  
        if not self.employee_id:
            return result
        
        employee = self.employee_id
        if self.holiday_status_id:
            hs_data = self.holiday_status_id.read(['ex_rest_days', 'ex_public_holidays', 'min_days'])[0]
        else:
            hs_data = {}
        ex_rd = hs_data.get('ex_rest_days', False)
        ex_ph = hs_data.get('ex_public_holidays', False)
        min_days = hs_data.get('min_days')
        
        # Get rest day and the schedule start time on the date the leave begins
        #
        rest_days = []
        if employee.contract_id and employee.contract_id.schedule_template_id:
            rest_days = sched_tpl_obj.get_rest_days(employee.contract_id.schedule_template_id.id)
        
        from_weekday = dt.weekday()          
        
        '''
            0 Monday
            1 Tuesday
            2 Wednesday
            3 Thursday
            4 Friday
            ->5 Saturday
            ->6 Sunday
        '''
         
        # If Date from start from the weekend make start from the first working day.
        if from_weekday == 4 and len(rest_days) == 2:
            dt += timedelta(days=+2)
            from_weekday = 6
        if from_weekday == 4 and len(rest_days) == 1:
            dt += timedelta(days=+1)
            from_weekday = 5
        if from_weekday == 5 and len(rest_days) == 2:
            dt += timedelta(days=+1)
            from_weekday = 6
        
        # If next date of date is weekend set as date to
#         pre_worked_date = dt_to
#         while (pre_worked_date.weekday() in rest_days) or (holiday_obj.is_public_holiday(pre_worked_date.date())):            
#             pre_worked_date += timedelta(days=-1)
#             dt_to = pre_worked_date
        
        # Get warning that you can't start from weekend,
        '''
        if from_weekday == 4:
            raise osv.except_osv(_('Warning'),'You can not start you leave from a weekend, the system will automatically choose your first working day.')
        if from_weekday == 5 and len(rest_days)==2:
            raise osv.except_osv(_('Warning'),'You can not start you leave from a weekend, the system will automatically choose your first working day')
        '''

        # Compute and update the number of days
        if (dt_to and dt) and (dt <= dt_to):
            td = dt_to - dt
            diff_day = td.days + float(td.seconds) / 86400
            number_of_days_temp = round(math.floor(diff_day)) + 1
        else:
            number_of_days_temp = 0
        
        count_days = number_of_days_temp
        real_days = 0
        ph_days = 0
        r_days = 0
        real_hours = 0.0
        working_days = 0
        next_dt = dt
        
        if self.partial_leave and self.date_time_from and self.date_time_to:
            real_hours = self._get_number_of_days(self.date_time_from, self.date_time_to, self.employee_id.id)      
       
        if not self.half_day and not self.partial_leave:
            while count_days > 0:
                public_holiday = holiday_obj.is_public_holiday(next_dt.date())
                if public_holiday and ex_ph:
                    ph_days += 1
                # public_holiday = (public_holiday and ex_ph)
                rest_day = (next_dt.weekday() in rest_days)
                if rest_day:
                    r_days += 1
                    if not ex_rd:
                        real_days += 1
                if not rest_day and not public_holiday:
                    working_days += 1
                    real_days += 1
                next_dt += timedelta(days=+1)
                count_days -= 1
                # if (next_dt.weekday() in rest_days):
                #     r_days += 1
                #     if not ex_rd:
                #         real_days += 1      
                # if not (next_dt.weekday() in rest_days) and public_holiday: 
                #     ph_days += 1
                #     if not ex_ph:
                #         real_days += 1
                # if not(next_dt.weekday() in rest_days) and not public_holiday:
                #     real_days += 1
                #     working_days += 1
                # count_days -= 1
        elif self.half_day:
            public_holiday = holiday_obj.is_public_holiday(next_dt.date())
            if not(next_dt.weekday() in rest_days) and not public_holiday:
                real_days = 0.5
                working_days = 0.5
            
        real_days_so_far = real_days
        
        return_date = dt_to + timedelta(days=+1)
        
        f = 0
        if len(rest_days) == 1:
            f = 3
        else:
            f = 2      
        
        
        include_exclude_date = []
        if (from_weekday + f) % 7 > min_days:
            if (from_weekday + f) % 7 + real_days_so_far > 7 and ex_rd:
#                 real_days -= len(rest_days)
                for rdays in rest_days:
                    rl = (rdays + f) - (from_weekday + f)
                    tdate = dt + timedelta(days=+rl)
                    tdate_v = tdate.strftime('%Y-%m-%d')
                    exclude_date_data = {'tdate': tdate_v, 'date_type': 'e', 'status': 'n', 'employee_id': self.employee_id.id}
                    include_exclude_date.append(exclude_date_data)
        # raise osv.except_osv(_('Warning1'),tdate_v)
                
        return_date_weekday = return_date.weekday()
        
        if (return_date_weekday + f) < min_days:
            if real_days > min_days:
                real_days += len(rest_days)
                for rdays in rest_days:
                    rl = (rdays + f) - (return_date_weekday + f)
                    itdate = dt + timedelta(days=+rl)
                    itdate_v = itdate.strftime('%Y-%m-%d')
                    include_date_data = {'tdate': itdate_v, 'date_type': 'i', 'status': 'n', 'employee_id': self.employee_id.id}
                    include_exclude_date.append(include_date_data)
        # raise osv.except_osv(_('Warning'),include_date)
                
        total_days = working_days + ph_days + r_days
        
        # Return Remaing Leaves

        if self.holiday_status_id and self.employee_id:
            leaves_bal = self.holiday_status_id.get_days(self.employee_id.id)[self.holiday_status_id.id]
            max_leaves = leaves_bal['max_leaves']
            leaves_taken = leaves_bal['leaves_taken']
            remaining_leaves = leaves_bal['remaining_leaves']
            curr_remaining_leaves = remaining_leaves - real_days
        else:
            max_leaves = 0
            leaves_taken = 0
            remaining_leaves = 0
            curr_remaining_leaves = 0
        flag = False
        flag_emp = False
        if self.holiday_status_id:
            flag = self.holiday_status_id.attachment_mandatory
            flag_emp = self.holiday_status_id.alternative_emp_mandatory
            
        hours_to_day = 0.0
        if real_hours:
            hours_to_day = (real_hours / HOURS_PER_DAY)            
            curr_remaining_leaves = remaining_leaves - hours_to_day
            
    
        vals= {'department_id':  employee.department_id.id ,
                'working_days_value': working_days,
                'rest_days_value': r_days,
                'public_holiday_days_value': ph_days,
                'real_days_value': real_days,
                'total_days_value': total_days,
                'working_days': working_days,
                'rest_days': r_days,
                'real_hours_value': real_hours,
                'real_hours': real_hours,
                'public_holiday_days': ph_days,
                'real_days': real_days,
                'total_days': total_days,
                'number_of_days_temp': hours_to_day or real_days,
                'return_date': return_date.strftime('%B %d, %Y'),
                'return_date_value': return_date.strftime('%B %d, %Y'),
                'max_leaves': max_leaves,
                'max_leaves_value': max_leaves,
                'remaining_leaves': remaining_leaves,
                'remaining_leaves_value': remaining_leaves,
                'curr_remaining_leaves': curr_remaining_leaves,
                'curr_remaining_leaves_value': curr_remaining_leaves,
                'leaves_taken': leaves_taken,
                'leaves_taken_value': leaves_taken,
                'include_exclude_lines': include_exclude_date,
                'flag_attachment':flag,
                'flag_emp_mandatory':flag_emp,
                'alternative_emp_id': '',
                'emp_id_view':employee.id}
        
        for name,value in vals.iteritems():
            setattr(self, name, value)
            
        if self.employee_id and self.holiday_status_id.allow_future_balance:
            self.future_balance_value = self._calculate_emp_future_accrued_days(self.employee_id.sudo())
        else:
            self.future_balance_value = 0
            
        self.max_allowed_days_value = self.future_balance_value + vals['max_leaves_value']
                
        return result
    
    #@api.multi
    def _send_mail(self, template_xmlid):
        if '.' not in template_xmlid:
            template_xmlid = 'hr_holidays_extension.%s' % template_xmlid
        self.env.ref(template_xmlid).send_mail(self.id)
                            
                        
    #@api.multi
    def action_draft(self):
        for holiday in self:
            if not holiday.can_reset:
                raise UserError(_('Only an HR Manager or the concerned employee can reset to draft.'))
            if holiday.state in ['validate']:
                raise UserError(_('Leave request state must be "Refused" or "To Approve" in order to reset to Draft.'))
            holiday.write({
                'state': 'draft',
                'manager_id': False,
                'manager_id2': False,
            })
            linked_requests = holiday.mapped('linked_request_ids')
            for linked_request in linked_requests:
                linked_request.action_draft()
            linked_requests.unlink()
            holiday.requster_cancel = False
            holiday._send_mail('email_template_holidays_update_emp3')
        return True
    
    #@api.multi
    def action_requester_cancel(self):
        self.state = 'requster_cancel'
        self.requster_cancel = True
        self._send_mail('email_template_holidays_request_cancel')
        
        
    #@api.multi
    def action_manager_refuse_cancellation(self):
        self.state = 'validate'
        self._send_mail('email_template_holidays_cancel_refused_mgt')
    
    #@api.multi
    def action_cancel(self):
        for holiday in self:
            holiday.write({
                'state': 'cancel',
            })
            if holiday.type=='remove':
                holiday.env['hr.attendance.date'].sudo().search([('employee_id','=', holiday.employee_id.id), ('date', '>=', holiday.date_from[:10]), ('date', '<=', holiday.date_to[:10])])._compute()
        return True
    
    #@api.multi
    def _checkWarning(self):
        self = self.sudo()
        for record in self:
            if record.state !='draft':
                raise UserError(_('Leave request must be in Draft state ("To Submit") in order to confirm it.'))
            
            if not record.empl_contract_id:
                raise Warning(_('There is no a valid contract for this employee, Please contact the human resources administration'))        
            
            if record.type == 'add':
                return
            
            if not record.employee_id:
                raise Warning(_('You cannot send the request without selecting an employee'))
            
            if record.ex_leave:
                return
            
            if not record.employee_id.parent_id:
                raise Warning(_('There is no manager for this employee.'))
            
            if not record.employee_id.parent_id.user_id:
                raise Warning(_('This employee manager dose not linked to a system user.'))
            
            if record.real_days > 1 and record.holiday_status_id.code == 'SLWR':
                raise Warning(_('You cannot request more than 1 individual leave day.'))
            
            if record.real_days and record.holiday_status_id.max_days and record.real_days > record.holiday_status_id.max_days:
                raise Warning(_('You cannot request more than %s leave day(s)') % record.holiday_status_id.max_days)            
            
            if record.empl_contract_id.trial_date_end > fields.Date.today() and not record.holiday_status_id.allow_trial_period:
                raise Warning(_('You cannot apply for this leave type while you are in the trial period.\n Please contact the HR department.'))
            
            if record.holiday_status_id.attachment_mandatory and not self.env['ir.attachment'].search([('res_model','=', self._name), ('res_id','=', record.id)], count = True):
                raise Warning(_('You cannot send the request to the manager without attaching a document.\n For attaching a document: press save then attach a document.'))
            
            if record.type=='remove' and not record.delegation_ignored:
                if not record.sudo().delegation_id or record.sudo().delegation_id.empty:
                    raise Warning('Enter delegation details')
            # change message and set the holiday code
            
            
            
    #@api.multi
    def action_confirm(self):            
        self.filtered(lambda record: record.state=='draft').action_approve()
                        
    #@api.multi
    def action_approve(self):
        for record in self:
            if record.state=='draft':
                record._checkWarning()
            if record.state == 'requster_cancel':
                record.state = 'cancel'
                record.sudo()._action_refuse()
                self.env['hr.attendance.date'].sudo().search([('employee_id','=', record.employee_id.id), ('date', '>=', record.date_from[:10]), ('date', '<=', record.date_to[:10])])._compute()
                self._send_mail('email_template_holidays_cancel_mgt')
        self._base('approval.record').action_approve(self)
        
    #@api.multi
    def _on_approve(self):
        self._action_validate(access_check = False)
        if self.type=='remove':
            self._send_mail('email_template_holidays_update_emp')
            self.env['hr.attendance.date'].sudo().search([('employee_id','=', self.employee_id.id), ('date', '>=', self.date_from[:10]), ('date', '<=', self.date_to[:10])])._compute()
        
    #@api.multi
    def _on_approval(self, old_state, new_state):
        manager_id = self.env.user.employee_ids[:1]
        if not self.manager_id:
            self.manager_id = manager_id       
        elif not self.manager_id2:
            self.manager_id2 = manager_id 
                         
    #@api.multi
    def _action_validate(self, access_check = True):
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user') and access_check:
            raise UserError(_('Only an HR Officer or Manager can approve leave requests.'))

        manager = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        for holiday in self:
            if holiday.state not in ['confirm', 'validate1'] and access_check:
                raise UserError(_('Leave request must be confirmed in order to approve it.'))
            if holiday.state == 'validate1' and not holiday.env.user.has_group('hr_holidays.group_hr_holidays_manager') and access_check:
                raise UserError(_('Only an HR Manager can apply the second approval on leave requests.'))
            
            holiday.write({'state': 'validate'})
            if holiday.double_validation:
                holiday.write({'manager_id2': manager.id})
            else:
                holiday.write({'manager_id': manager.id})
            if holiday.holiday_type == 'employee' and holiday.type == 'remove':
                meeting_values = {
                    'name': holiday.display_name,
                    'categ_ids': [(6, 0, [holiday.holiday_status_id.categ_id.id])] if holiday.holiday_status_id.categ_id else [],
                    'duration': holiday.number_of_days_temp * HOURS_PER_DAY,
                    'description': holiday.notes,
                    'user_id': holiday.user_id.id,
                    'start': holiday.date_from,
                    'stop': holiday.date_to,
                    'allday': False,
                    'state': 'open',            # to block that meeting date in the calendar
                    'privacy': 'confidential'
                }
                #Add the partner_id (if exist) as an attendee
                if holiday.user_id and holiday.user_id.partner_id:
                    meeting_values['partner_ids'] = [(4, holiday.user_id.partner_id.id)]

                meeting = self.env['calendar.event'].with_context(no_mail_to_attendees=True).create(meeting_values)
                holiday.sudo()._create_resource_leave()
                holiday.write({'meeting_id': meeting.id})
            elif holiday.holiday_type == 'category':
                leaves = self.env['hr.leave']
                for employee in holiday.category_id.employee_ids:
                    values = holiday._prepare_create_by_category(employee)
                    leaves += self.with_context(mail_notify_force_send=False).create(values)
                # TODO is it necessary to interleave the calls?
                leaves.action_approve()
                if leaves and leaves[0].double_validation:
                    leaves.action_validate()
                    
        unlink_ids = []
        det_obj = self.env.get('hr.schedule.detail')
        for leave in self:
            if leave.type != 'remove':
                continue

            det_ids = det_obj.search(
                [(
                    'schedule_id.employee_id', '=', leave.employee_id.id),
                    ('date_start', '<=', leave.date_to),
                    ('date_end', '>=', leave.date_from)],
                order='date_start')
            for detail in det_ids:

                # Remove schedule details completely covered by leave
                if leave.date_from <= detail.date_start and leave.date_to >= detail.date_end:
                    if detail.id not in unlink_ids:
                        unlink_ids.append(detail.id)

                # Partial day on first day of leave
                elif leave.date_from > detail.date_start and leave.date_from <= detail.date_end:
                    dtLv = datetime.strptime(leave.date_from, OE_DTFORMAT)
                    if leave.date_from == detail.date_end:
                        if detail.id not in unlink_ids:
                            unlink_ids.append(detail.id)
                        else:
                            dtSchedEnd = dtLv + timedelta(seconds=-1)
                            detail.write({'date_end': dtSchedEnd.strftime(OE_DTFORMAT)})

                # Partial day on last day of leave
                elif leave.date_to < detail.date_end and leave.date_to >= detail.date_start:
                    dtLv = datetime.strptime(leave.date_to, OE_DTFORMAT)
                    if leave.date_to != detail.date_start:
                        dtStart = dtLv + timedelta(seconds=+1)
                        detail.write({'date_start': dtStart.strftime(OE_DTFORMAT)})

        det_obj.browse(unlink_ids).sudo().unlink()
        
        self.env['hr.holidays.days_include'].search([('request_id','in', self.ids)]).write({'status': 'a'})            
        
        for record in self:
            record.sudo().delegation_id.action_confirm()                
            
        return True
                
    
    #@api.multi
    def action_validate(self):
        self = self.filtered(lambda record: record.state not in ['validate'])
        return self._action_validate()
    
    #@api.multi
    def _action_refuse(self):
        for holiday in self:
            # Delete the meeting
            if holiday.meeting_id:
                holiday.meeting_id.unlink()
            # If a category that created several holidays, cancel all related
            holiday.linked_request_ids.action_refuse()
        self._remove_resource_leave()
        return True    
                
    #@api.multi
    def action_refuse(self):
        res = super(Holidays, self).action_reject()
        if self.state!=self._reject_state:
            return
        self._action_refuse()
        self.env['hr.holidays.days_include'].search([('request_id','in', self.ids)]).write({'status': 'n'})
        sched_obj = self.env.get('hr.schedule')
        for leave in self:
            if leave.type != 'remove':
                continue

            dLvFrom = datetime.strptime(leave.date_from, OE_DTFORMAT).date()
            dLvTo = datetime.strptime(leave.date_to, OE_DTFORMAT).date()
            sched_ids = sched_obj.search([('employee_id', '=', leave.employee_id.id),
                          ('date_start', '<=', dLvTo.strftime(
                              OE_DFORMAT)),
                          ('date_end', '>=', dLvFrom.strftime(OE_DFORMAT))])

            # Re-create affected schedules from scratch
            for sched_id in sched_ids:
                sched_id.sudo().delete_details()
                sched_id.sudo().create_details()
        
        return res
    
    #@api.multi
    def action_view_delegation(self):
        self.ensure_one()
        self.env['delegation'].check_access_rights('read') 
        context = dict(self._context, 
                       default_date_from = self.date_from,
                       default_date_to = self.date_to )
        if self.state == 'draft' and self.env['delegation'].check_access_rights('write', raise_exception = False):
            mode = 'edit'
            view_id = self.env.ref('delegation.view_delegation_form').id
        else:
            mode = 'view'
            view_id = self.env.ref('delegation.view_delegation_form_read').id
            
        if not self.delegation_id:
            self.env['delegation'].check_access_rights('create') 
            self.delegation_id = self.env['delegation'].create({'date_from' : self.date_from,
                                       'date_to' : self.date_to,
                                       'leave_id' : self.id,
                                       'employee_id' : self.employee_id.id,
                                       'user_id' : self.employee_id.user_id.id,
                                       'lines' : self._get_delegation_lines()
                                       })
                    
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'delegation',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
            'view_id' : view_id,
            'res_id': self.delegation_id.id,
            'name' :'Delegation',
            'flags': {'form': {'action_buttons': False, 'options': {'mode': mode}}},
        }        
       
    @api.model
    def _get_delegation_lines(self):
        lines =[]
        groups = []
        for group in self.env.user.groups_id:
            if group.allow_delegation:
                groups.append((group.display_name, group))
        for _, group in sorted(groups):
            lines.append((0,0, {'group_id': group.id,'date_from': self.date_from,'date_to': self.date_to,'state': 'draft'}))
        return lines    
    
    @api.depends('delegation_id')
    def _calc_delegation_count(self):
        for record in self:
            if record.delegation_id:
                record.delegation_name = '1'
            else:
                record.delegation_name = '0'
    
    #@api.multi
    def unlink(self):
        for record in self:
            if record.payroll_period_state == 'locked' and not record.holiday_status_id.ignore_locked_period:
                raise Warning(_('You cannot delete a leave request which exist in a locked payroll period. \n Please, contact the HR department.'))
            return super(Holidays, self).unlink()
    
    #@api.multi
    def write(self, vals):
        if 'state' in vals:
            for record in self:
                if record.payroll_period_state == 'locked' and not record.holiday_status_id.ignore_locked_period:
                    raise Warning(_('You cannot modify a leave request which exist in a locked payroll period. \n Please, contact the HR department.'))
        res= super(Holidays, self).write(vals)
        for record in self.sudo().filtered(lambda record: record.delegation_ignored and record.delegation_id):
            if record.delegation_id.state =='draft':
                record.delegation_id.unlink()
            record.delegation_id = False            
        return res
    
    @api.model
    def  _get_employee_accrual_line_policy(self, employee_id):
        if 'hr.policy.line.accrual' not in self.env:
            return False
        return employee_id.contract_id.policy_group_id.get_latest_accrual_policy().line_ids[-1:]
        
    @api.model
    def  _get_last_allocation_day(self, employee_id):
        calculation_frequency = ''
        last_allocation_day = 0
        accrual_line_policy = self._get_employee_accrual_line_policy(employee_id)
        if accrual_line_policy:
            calculation_frequency = accrual_line_policy.calculation_frequency
            if accrual_line_policy.frequency_on_hire_date:
                initial_employment_date = employee_id.initial_employment_date
                if initial_employment_date:
                    initial_employment_date = fields.Date.from_string(initial_employment_date)
                    if calculation_frequency =='weekly':
                        last_allocation_day = initial_employment_date.weekday()
                    elif calculation_frequency =='monthly':
                        last_allocation_day = initial_employment_date.day
                    elif calculation_frequency =='annual':
                        frequency_annual_month = initial_employment_date.month
                        frequency_annual_day = initial_employment_date.day
                        last_allocation_day = frequency_annual_day + '/' + frequency_annual_month
            else:
                if calculation_frequency =='weekly':
                    last_allocation_day = accrual_line_policy.frequency_week_day
                elif calculation_frequency =='monthly':
                    last_allocation_day = accrual_line_policy.frequency_month_day
                elif calculation_frequency =='annual':
                    frequency_annual_month = accrual_line_policy.frequency_annual_month
                    frequency_annual_day = accrual_line_policy.frequency_annual_day
                    last_allocation_day = frequency_annual_day + '/' + frequency_annual_month
        return calculation_frequency, last_allocation_day
    
    @api.model
    def  _get_employee_daily_accrual_date(self, employee_id):
        accrual_rate, daily_accrual_rate = 2.5, 0.083333
        accrual_line_policy = self._get_employee_accrual_line_policy(employee_id)
        if accrual_line_policy:
            accrual_rate = accrual_line_policy.accrual_rate
            calculation_frequency = accrual_line_policy.calculation_frequency
            if calculation_frequency =='weekly':
                daily_accrual_rate = accrual_rate / 7
            elif calculation_frequency =='monthly':
                daily_accrual_rate = accrual_rate / 30
            elif calculation_frequency =='annual':
                daily_accrual_rate = accrual_rate / 360
        return daily_accrual_rate        
        
    @api.model
    def _calculate_emp_future_accrued_days(self, employee_id, date_from):
        date_diff = 0
        today, future_calculation_start = date.today(), date.today()
        leave_date_from = datetime.strptime(date_from[:10], '%Y-%m-%d').date()
        if leave_date_from <= today:
            leave_date_from = today
        calculation_frequency, last_allocation_day = self._get_last_allocation_day(employee_id)
        if calculation_frequency and last_allocation_day:
            if calculation_frequency =='monthly' or calculation_frequency =='annual':
                if calculation_frequency =='monthly':
                    future_calculation_start = datetime(today.year, today.month, int(last_allocation_day)).date()
                    # if leave_date_from <= today:
                    #     leave_date_from = today
                elif calculation_frequency =='annual':
                    last_allocation_year_day = last_allocation_day.split('/')[0]
                    last_allocation_year_month = last_allocation_day.split('/')[1]
                    future_calculation_start = datetime(today.year, int(last_allocation_year_month), int(last_allocation_year_day)).date()
                date_diff = (leave_date_from - future_calculation_start).days
            elif calculation_frequency =='weekly':
                today_weekday = today.weekday()
                last_allocation_day_date = int(today_weekday) - int(last_allocation_day)
                if last_allocation_day_date <= 0 :
                    last_allocation_day_date = last_allocation_day_date + 7
                future_calculation_start = today - timedelta(days = last_allocation_day_date)
                date_diff = (leave_date_from - future_calculation_start).days
        
        daily_accrual_rate = self._get_employee_daily_accrual_date(employee_id)
        emp_future_accrued_days = date_diff * daily_accrual_rate
        return emp_future_accrued_days
        
        
    @api.constrains('state', 'number_of_days_temp')
    def _check_holidays(self):
        for holiday in self:
            if holiday.holiday_type != 'employee' or holiday.type != 'remove' or not holiday.employee_id or holiday.holiday_status_id.limit:
                continue
            leave_days = holiday.holiday_status_id.get_days(holiday.employee_id.id)[holiday.holiday_status_id.id]
            if float_compare(leave_days['remaining_leaves'], holiday.future_balance, precision_digits=2) == -1 or \
              float_compare(leave_days['virtual_remaining_leaves'], holiday.future_balance, precision_digits=2) == -1:
                raise ValidationError(_('The number of remaining leaves is not sufficient for this leave type.\n'
                                        'Please verify also the leaves waiting for validation.'))
                
                
    @api.depends('employee_id', 'holiday_status_id')
    def _calc_my_balance(self):
        for record in self.filtered(lambda leave: leave.holiday_status_id.code == 'LVANNUAL'):
            leaves_bal = self.remaining_leaves
            if not leaves_bal:
                leaves_bal = self.holiday_status_id.get_days(record.employee_id.id) and self.holiday_status_id.get_days(record.employee_id.id)[record.holiday_status_id.id] or False
            if isinstance(leaves_bal, dict):
                leaves_bal = leaves_bal['remaining_leaves']
            if not leaves_bal:
                continue
            days = int(leaves_bal)
            hours = int((leaves_bal - days) * 8)
            minutes = (((leaves_bal - days) * 8) - hours) * 60
            minutes = round(minutes, 2)
            res = []
            res.append('Day: %s' % (days))
            res.append('Hours: %s' % (hours))
            res.append('Minutes: %s' % (minutes))
            record.leave_balance_char = ', '.join(res)        
    
    @api.depends('curr_remaining_leaves')
    def _calc_my_new_balance(self):
        for record in self.filtered(lambda leave: leave.holiday_status_id.code == 'LVANNUAL'):
            if record.curr_remaining_leaves:
                res = []
                days = int(record.curr_remaining_leaves)
                hours = int((record.curr_remaining_leaves - days) * 8)
                minutes = (((record.curr_remaining_leaves - days) * 8) - hours) * 60
                minutes = round(minutes, 2)
                res.append('Day: %s' % (days))
                res.append('Hours: %s' % (hours))
                res.append('Minutes: %s' % (minutes))
                record.new_leave_balance_char = ', '.join(res)
                
    @api.depends('real_hours_value','date_from','date_to')
    def _calc_taken_hours(self):
        for record in self.filtered(lambda leave: leave.holiday_status_id.code == 'LVANNUAL' and leave.real_hours_value):
            hours = int(record.real_hours_value)
            minutes = (record.real_hours_value - hours) * 60
            minutes = int(round(minutes, 0))
            record.total_hours_char = '%s hours and %s minutes' % (hours,minutes)
            
    def get_timezone_from_datetime(self, datetime_str):
        dt = fields.Datetime.from_string(datetime_str)
        dt = dt + timedelta(hours=+3)
        return str(dt)
                               
                
    def _get_number_of_days(self, date_from, date_to, employee_id):
        """ Returns a float equals to the timedelta between two dates given as string."""
        from_dt = fields.Datetime.from_string(date_from)
        to_dt = fields.Datetime.from_string(date_to)

        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            resource = employee.resource_id.sudo()
            if resource and resource.calendar_id:
                hours = resource.calendar_id.get_working_hours(from_dt, to_dt, resource_id=resource.id, compute_leaves=True)
                uom_hour = resource.calendar_id.uom_id
                uom_day = self.env.ref('product.product_uom_day')
                if uom_hour and uom_day:
                    return uom_hour._compute_quantity(hours, uom_day, round=False)

        time_delta = to_dt - from_dt
        return math.ceil(time_delta.days + float(time_delta.seconds) / 86400)
    
    #@api.multi
    @api.depends('sla_state')
    def _compute_state_icon(self):            
        for record in self:
            record.state_icon = '/hr_holidays_extension/static/src/img/icons/%s.png' % record.sla_state
            
    @api.depends('state')
    def _compute_sla_state(self):
        today = fields.Date.from_string(fields.Date.today())
        for record in self:
            found = False
            for line in self.env['hr.holidays.approval'].search([]):
                if line.state == record.state and record.approval_logs:
                    from_date = fields.Date.from_string(record.approval_logs[0].date)
                    if from_date:
                        delta = today - from_date
                        if delta.days < line.sla_date_count:
                            record.sla_state = 'green'
                        elif delta.days == line.sla_date_count:
                            record.sla_state = 'yellow'
                        else:
                            record.sla_state = 'red'
                    found = True
                    break
            if not found:
                record.sla_state = 'gray'
        
               
                                     
                                                    
