
export AWS_ACCESS_KEY_ID=`curl -H "Authorization: $AWS_CONTAINER_AUTHORIZATION_TOKEN" $AWS_CONTAINER_CREDENTIALS_FULL_URI | jq -r '.AccessKeyId'`
export AWS_SECRET_ACCESS_KEY=`curl -H "Authorization: $AWS_CONTAINER_AUTHORIZATION_TOKEN" $AWS_CONTAINER_CREDENTIALS_FULL_URI | jq -r '.SecretAccessKey'`
export AWS_SESSION_TOKEN=`curl -H "Authorization: $AWS_CONTAINER_AUTHORIZATION_TOKEN" $AWS_CONTAINER_CREDENTIALS_FULL_URI | jq -r '.Token'`


#/bin/rm -rf ~/.aws/credentials
#echo '[spp]' > ~/.aws/credentials
###aws configure set profile.spp.aws_access_key_id $AWS_ACCESS_KEY_ID
###aws configure set profile.spp.aws_secret_access_key $AWS_SECRET_ACCESS_KEY
