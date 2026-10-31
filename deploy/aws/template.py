"""Small CloudFormation stack for one persistent, SSM-managed demo server."""

from pathlib import Path


def ref(name):
    return {"Ref": name}


def sub(value):
    return {"Fn::Sub": value}


def resource(kind, **properties):
    return {"Type": "AWS::" + kind, "Properties": properties}


def build_template():
    resources = {
        "Vpc": resource("EC2::VPC", CidrBlock="10.42.0.0/16", EnableDnsSupport=True, EnableDnsHostnames=True),
        "Gateway": resource("EC2::InternetGateway"),
        "GatewayAttachment": resource("EC2::VPCGatewayAttachment", VpcId=ref("Vpc"), InternetGatewayId=ref("Gateway")),
        "Subnet": resource("EC2::Subnet", VpcId=ref("Vpc"), CidrBlock="10.42.0.0/24", MapPublicIpOnLaunch=True),
        "RouteTable": resource("EC2::RouteTable", VpcId=ref("Vpc")),
        "DefaultRoute": {**resource("EC2::Route", RouteTableId=ref("RouteTable"),
                                   DestinationCidrBlock="0.0.0.0/0", GatewayId=ref("Gateway")),
                         "DependsOn": "GatewayAttachment"},
        "RouteAssociation": resource("EC2::SubnetRouteTableAssociation", SubnetId=ref("Subnet"), RouteTableId=ref("RouteTable")),
        "SecurityGroup": resource("EC2::SecurityGroup", VpcId=ref("Vpc"),
            GroupDescription="Public HTTPS and ACME HTTP only; management via SSM, no SSH",
            SecurityGroupIngress=[{"IpProtocol": "tcp", "FromPort": port, "ToPort": port, "CidrIp": "0.0.0.0/0"}
                                  for port in (80, 443)]),
        "Artifacts": {**resource("S3::Bucket",
            PublicAccessBlockConfiguration={key: True for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")},
            OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
            BucketEncryption={"ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
            LifecycleConfiguration={"Rules": [{"Id": "ExpireReleaseArchives", "Status": "Enabled", "Prefix": "releases/", "ExpirationInDays": 14}]}),
            "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"},
        "ArtifactPolicy": resource("S3::BucketPolicy", Bucket=ref("Artifacts"), PolicyDocument={
            "Version": "2012-10-17", "Statement": [{"Effect": "Deny", "Principal": "*", "Action": "s3:*",
            "Resource": [sub("${Artifacts.Arn}"), sub("${Artifacts.Arn}/*")],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}),
        "Role": resource("IAM::Role", AssumeRolePolicyDocument={"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            Policies=[{"PolicyName": "StreamChatRuntime", "PolicyDocument": {"Version": "2012-10-17", "Statement": [
                {"Effect": "Allow", "Action": ["ssm:UpdateInstanceInformation", "ssm:DescribeAssociation", "ssm:GetDocument",
                    "ssm:DescribeDocument", "ssm:ListAssociations", "ssm:ListInstanceAssociations",
                    "ssm:UpdateAssociationStatus", "ssm:UpdateInstanceAssociationStatus"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel",
                    "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"], "Resource": "*"},
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": sub("${Artifacts.Arn}/releases/*")},
                {"Effect": "Allow", "Action": "ssm:GetParameter",
                    "Resource": sub("arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AWS::StackName}/runtime")},
                {"Effect": "Allow", "Action": "kms:Decrypt", "Resource": "*", "Condition": {"StringEquals": {
                    "kms:ViaService": sub("ssm.${AWS::Region}.amazonaws.com"),
                    "kms:EncryptionContext:PARAMETER_ARN": sub("arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AWS::StackName}/runtime")}}}
            ]}}]),
        "Profile": resource("IAM::InstanceProfile", Roles=[ref("Role")]),
        "Instance": {**resource("EC2::Instance", ImageId=ref("UbuntuAmi"), InstanceType=ref("InstanceType"),
            IamInstanceProfile=ref("Profile"), SubnetId=ref("Subnet"), SecurityGroupIds=[ref("SecurityGroup")],
            CreditSpecification={"CPUCredits": "standard"},
            MetadataOptions={"HttpTokens": "required", "HttpPutResponseHopLimit": 1, "HttpEndpoint": "enabled"},
            BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {
                "VolumeType": "gp3", "VolumeSize": 16, "Encrypted": True, "DeleteOnTermination": False}}],
            PropagateTagsToVolumeOnCreation=True,
            Tags=[{"Key": "Name", "Value": ref("AWS::StackName")}, {"Key": "Application", "Value": "StreamChat"}],
            UserData={"Fn::Base64": Path(__file__).with_name("bootstrap.sh").read_text(encoding="utf-8")}),
            "DependsOn": ["DefaultRoute", "RouteAssociation"]},
        "Address": resource("EC2::EIP", Domain="vpc"),
        "AddressAssociation": resource("EC2::EIPAssociation", InstanceId=ref("Instance"), AllocationId={"Fn::GetAtt": ["Address", "AllocationId"]}),
    }
    return {"AWSTemplateFormatVersion": "2010-09-09", "Description": "Stream Chat single-instance AWS demo (credit usage applies)",
        "Parameters": {
            "DomainName": {"Type": "String", "Description": "Public hostname controlled by the operator; no scheme or path"},
            "InstanceType": {"Type": "String", "Default": "t3.micro", "AllowedValues": ["t3.micro", "t3.small"]},
            "UbuntuAmi": {"Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
                "Default": "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"}},
        "Resources": resources, "Outputs": {
            "InstanceId": {"Value": ref("Instance")}, "PublicIp": {"Value": ref("Address")},
            "ArtifactBucket": {"Value": ref("Artifacts")}, "DomainName": {"Value": ref("DomainName")},
            "PublicUrl": {"Value": sub("https://${DomainName}")},
            "CallbackUrl": {"Value": sub("https://${DomainName}/oauth/chzzk/callback")},
            "RuntimeParameter": {"Value": sub("/${AWS::StackName}/runtime")},
            "DeploymentKind": {"Value": "StreamChatSingleInstanceV1"}}}
