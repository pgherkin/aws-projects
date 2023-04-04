#Version: 0.2

import io
import re
import time
import boto3
import pandas as pd

params = {
    'region': 'eu-west-2',
    'database': 'mydatabase',
    'bucket': 'athena-test-dataset1',
    'path': 'results',
    'workgroup': 'removed',
    'query': 'SELECT * FROM tbldata LIMIT 10',
    'accesskey': 'removed',
    'secretkey': 'removed'
}

#start aws session
session = boto3.Session(
    aws_access_key_id = params['accesskey'],
    aws_secret_access_key = params['secretkey']
)
client = session.client('athena', region_name=params['region'])

def execute_query(client, params):
    response = client.start_query_execution(
        QueryString=params["query"],
        QueryExecutionContext={
            'Database': params['database']
        },
        ResultConfiguration={
            'OutputLocation': 's3://' + params['bucket'] + '/' + params['path']
        }
        #added by DL
        #WorkGroup=params['workgroup']
    )
    return response

def get_query_state(execution_id):
    response = client.get_query_execution(QueryExecutionId=execution_id)
    if (
        "QueryExecution" in response
        and "Status" in response["QueryExecution"]
        and "State" in response["QueryExecution"]["Status"]
    ):
        state = response["QueryExecution"]["Status"]["State"]
    else:
        state = 'UNKNOWN'

    return state

def are_results_available(execution_id):
	state = get_query_state(execution_id=execution_id)
	print(f"Query state: {state}")
	
	while (state in ['RUNNING', 'QUEUED']):
		time.sleep(3)
		state = get_query_state(execution_id=execution_id)
		print(f"Query state: {state}")

	if state == 'SUCCEEDED':
		print("Fetching results...")
		return True
	elif state == 'FAILED':
		raise Exception("Query failed")

	return False

def get_results_data(execution_id):
    response = client.get_query_results(
        QueryExecutionId=execution_id
    )

    results = response['ResultSet']['Rows']
    return results

def get_results_filename(execution_id):
    response = client.get_query_execution(QueryExecutionId = execution_id)
    s3_path = response['QueryExecution']['ResultConfiguration']['OutputLocation']
    filename = re.findall('.*\/(.*)', s3_path)[0]
    return filename

def format_results(session, params, s3_filename):    
    s3client = session.client('s3')
    obj = s3client.get_object(Bucket=params['bucket'],
                              Key=params['path'] + '/' + s3_filename)
    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    return df

def main():
    #run athena query
    execution = execute_query(client, params)
    execution_id = execution['QueryExecutionId']
    print(f"Query execution id: {execution_id}")

    #check execution status
    if are_results_available(execution_id=execution_id):
        #get results filename
        s3_filename = get_results_filename(execution_id=execution_id)
        #format data into dataframe
        df = format_results(session, params, s3_filename)
        #show results
        print('Query Results:')
        print(df)

if __name__ == "__main__":
    main()
