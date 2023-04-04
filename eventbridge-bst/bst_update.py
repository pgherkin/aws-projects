"""
In the UK the clocks go forward 1 hour
at 1am on the last Sunday in March,
and back 1 hour at 2am on the last Sunday in October.

This script will determine if the clocks change today,
and then update the cron schedules for a list of CloudWatch events,
and send a notification of any failed or successful updates.

AC
"""

import os
import boto3
from datetime import date

account_alias = os.environ['AWS_ALIAS']
sns_topic_arn = os.environ['SNS_ARN'] 
parameter_key = os.environ['SSM_PARAM']

ssmps = boto3.client('ssm')
param = ssmps.get_parameter(Name=parameter_key)
rules = param['Parameter']['Value'].split(',')

today = date.today()

# Test_Mode
#today = today.replace(month=3, day=27)     # March 22
#today = today.replace(month=10, day=30)    # October 22


def lambda_handler(event, context):

    shift = shift_required(today)

    if shift == 1 or shift == -1:
        update_result = reschedule_rules(shift)

        email_sub = 'BST clock adjustment ' + account_alias
        email_msg = format_message(update_result, shift)

        send_notification(email_sub, email_msg)


def shift_required(input_date):
    # determines whether we need to shift the time today

    if ((today.month == 3 or today.month == 10)
        and today.day in range(25,31)
        and today.weekday() == 6       # last sunday of the month!
        ):

        if today.month ==  3:
            result = -1         #clocks forward in march, set UTC back
        elif today.month == 10:
            result = 1          #set timings forward, back to GMT+0

    else:
        result = 0

    return result


def reschedule_rules(input_shift):
    # updates the cloudwatch schedule for a given rule
    
    update_success = []
    update_failure = []

    sched = boto3.client('events')

    for rule_name in rules:

        current   = sched.describe_rule(Name=rule_name)
        cron      = current['ScheduleExpression']
        cron_exp  = cron[5:-1].split(' ')
        cron_hour = cron_exp[1]

        new_hour = update_cron_hour(cron_hour, input_shift) 

        cron_exp[1] = new_hour
        cron_exp    = " ".join(cron_exp)
        cron        = "cron(" + cron_exp + ")"

        try:
            sched.put_rule(
                Name=rule_name,
                ScheduleExpression=cron
                )
        except:
            # update failed
            update_failure.append(rule_name)
        else:
            # update succeeds
            update_success.append(rule_name)

    return update_success, update_failure


def update_cron_hour(input_hour, input_shift):
# Need to account for multiple hour values and ranges e.g. "18-23,0-2"
# hour_grps = "18-23","0-2"
# hour_rng = "18-23"
# hour_vals = "18","23"

    hour_grps = input_hour.split(',')
    for grp_num in range(0, len(hour_grps)):

        hour_rng = hour_grps[grp_num]
        hour_vals = hour_rng.split('-') 
        
        for val_num in range(0, len(hour_vals)):

            if input_shift == 1:
                # set hour forward
                if hour_vals[val_num] == '23':
                    hour_vals[val_num] = '0'
                else:
                    hour_vals[val_num] = int(hour_vals[val_num]) + 1

            elif input_shift == -1:
                # set hour back
                if hour_vals[val_num] == '0':
                    hour_vals[val_num] = '23'
                else:
                    hour_vals[val_num] = int(hour_vals[val_num]) - 1

            hour_vals[val_num] = str(hour_vals[val_num])

        hour_rng = "-".join(hour_vals)
        hour_grps[grp_num] = hour_rng

    new_cron_hour = ",".join(hour_grps)

    return new_cron_hour


def send_notification(input_sub, input_msg):
    # sends a message to an SNS topic

    notif = boto3.client('sns')

    response = notif.publish (
        TargetArn = sns_topic_arn,
        Message=input_msg,
        Subject=input_sub,
        MessageStructure='string',
        )


def format_message(input_result, input_shift):
    # formats an email message containing update statuses

    success = input_result[0]
    failure = input_result[1]

    if not success: success.append("None")
    if not failure: failure.append("None")

    if input_shift == 1: input_shift = '+1'

    email_msg = """
The clocks have changed today!
    
An attempt has been made to automatically adjusted the time
in a configured list of CloudWatch rules:

Time adjustment: {change}

SUCCESSFUL UPDATES
{yes}

FAILED UPDATES
{no}
""".format(
        change=input_shift,
        yes="\n".join(success),
        no="\n".join(failure)
        )

    return email_msg

