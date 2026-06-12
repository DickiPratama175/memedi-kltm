import os
import json
import multiprocessing as mp
from colorama import Fore, Style
import boto3
from botocore.exceptions import ClientError

def clear():
    if os.name == 'posix':
        _ = os.system('clear')
    elif os.name == 'nt':
        _ = os.system('cls')

clear()

colors = [Fore.LIGHTBLUE_EX]

text = """
    ╔══════════════════════════════════════════╗
    ║             SES LIMIT CHECKER            ║
    ║              ULTRAMEN KLTM               ║
    ╚══════════════════════════════════════════╝

FORMAT NYA TITIK DUA YA ULTRAMEN (:)
"""
banner = ""
for i, letter in enumerate(text):
    color = colors[i % len(colors)]
    banner += f"{color}{letter}{Style.RESET_ALL}"
print(banner)

regions = ["us-east-1"]

def check_send_quota(region, access_key_id, secret_access_key, healthy_file, shutdown_file):
    client = boto3.client('sesv2',
                          aws_access_key_id=access_key_id,
                          aws_secret_access_key=secret_access_key,
                          region_name=region)

    try:
        response = client.get_account()
        enforcement_status = response['EnforcementStatus']
        quota = response['SendQuota']['Max24HourSend']

        if enforcement_status == 'HEALTHY' and quota >= 200:
            enforcement_color = Fore.GREEN
            with open(healthy_file, "a") as healthy_file:
                healthy_file.write(f"{access_key_id}:{secret_access_key}:{region}:{quota}\n")
        elif enforcement_status == 'SHUTDOWN':
            enforcement_color = Fore.RED
            with open(shutdown_file, "a") as shutdown_file:
                shutdown_file.write(f"{access_key_id}:{secret_access_key}:{region}:{quota}\n")
        elif enforcement_status == 'PROBATION':
            enforcement_color = Fore.YELLOW
            with open("probo.txt", "a") as probo_file:
                probo_file.write(f"{access_key_id}:{secret_access_key}:{region}:{quota}\n")
        else:
            enforcement_color = Fore.CYAN

        message = f"{Fore.WHITE}{access_key_id}, {Fore.LIGHTBLUE_EX}Max 24h send quota for {Fore.YELLOW} {region}: {Fore.GREEN} {quota}{Fore.RESET} Status: {enforcement_color}{enforcement_status}"

        if enforcement_status == 'HEALTHY' and quota >= 200:
            print(f"{Fore.LIGHTGREEN_EX}[INFO] {Fore.WHITE}{message}")
        else:
            print(f"{Fore.LIGHTMAGENTA_EX}[INFO] {message}", Fore.CYAN)

    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            print(f"{Fore.LIGHTMAGENTA_EX}[ERROR] {Fore.RED} Unauthorized access for AWS Key: {access_key_id}")
        else:
            print(f"{Fore.LIGHTMAGENTA_EX}[ERROR] {Fore.RED} Invalid AWS Key: {access_key_id}")

def get_ec2_fargate_limits(access_key_id, secret_access_key, region):
    try:
        # Check EC2 limits
        client_quota = boto3.client('service-quotas', 
                                  aws_access_key_id=access_key_id, 
                                  aws_secret_access_key=secret_access_key, 
                                  region_name=region)
        
        ec2_quota = client_quota.get_service_quota(
            ServiceCode='ec2', 
            QuotaCode='L-1216C47A'
        )['Quota']['Value']
        
        # Check Fargate limits
        fargate_quota = client_quota.get_service_quota(
            ServiceCode='fargate', 
            QuotaCode='L-36FBB829'
        )['Quota']['Value']
        
        # Get IAM policies
        client_iam = boto3.client('iam', 
                                aws_access_key_id=access_key_id, 
                                aws_secret_access_key=secret_access_key, 
                                region_name=region)
        
        username = client_iam.get_user()['User']['UserName']
        policies = client_iam.list_user_policies(UserName=username)['PolicyNames']
        
        with open('ec2_fargate.txt', 'a') as f:
            policy_string = ', '.join(policies)
            f.write(f"{access_key_id}:{secret_access_key}:{region} | EC2: {ec2_quota} | Fargate: {fargate_quota} | Policies: {policy_string}\n")
            
    except Exception as e:
        print(f"{Fore.LIGHTMAGENTA_EX}[ERROR] {Fore.RED} Failed to get EC2/Fargate limits for {access_key_id}: {str(e)}")

def check_credentials(credentials_list, regions, healthy_file, shutdown_file):
    for credential in credentials_list:
        access_key_id, secret_access_key, region = credential.split(':')

        try:
            # Check SES quotas
            for r in regions:
                check_send_quota(r, access_key_id, secret_access_key, healthy_file, shutdown_file)
            
            # Add EC2/Fargate check for the original region
            get_ec2_fargate_limits(access_key_id, secret_access_key, region)
                
        except boto3.exceptions.Boto3Error as e:
            print(f"[ERROR] Invalid or unauthorized AWS Key {access_key_id}: {str(e)}")
            continue

if __name__ == "__main__":
    credentials_file = input('WHERE IS MONSTERS FOR CHECK? ')

    # Créer des fichiers distincts pour les états HEALTHY et SHUTDOWN
    healthy_file = "healthy.txt"
    shutdown_file = "shutdown.txt"

    with open(credentials_file, 'r') as f:
        credentials_list = [line.strip() for line in f]

    num_processes = 4
    processes = []

    for i in range(num_processes):
        process = mp.Process(target=check_credentials, args=(credentials_list[i::num_processes], regions, healthy_file, shutdown_file))
        process.start()
        processes.append(process)

    for process in processes:
        process.join()
