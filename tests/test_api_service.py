from src.lambda_services.api_service.api_service import generate_id_and_tokens
import json

def test_generate_id_and_tokens():
    test_api_gateway_event_without_jobid = {
        'bucket_name': 'sample-bucket',
        'file_list'  : ['file1.txt', 'file2.pdb', 'file3.csv'],
    }
    response = generate_id_and_tokens(test_api_gateway_event_without_jobid, None)
    print( json.dumps(response, indent=2) )

    test_api_gateway_event_with_jobid = {
        'bucket_name': 'sample-bucket',
        'file_list'  : ['file1.txt', 'file2.pdb', 'file3.csv'],
        'job_id'     : 'sampleJobID',
    }
    response = generate_id_and_tokens(test_api_gateway_event_with_jobid, None)
    print( json.dumps(response, indent=2) )
