from datadog_checks.base import AgentCheck
import boto3
import requests
from datetime import datetime, timezone

IMDS_BASE = "http://169.254.169.254"

class EksAmiAgeCheck(AgentCheck):
    def get_imds_token(self):
        token_resp = requests.put(
            f"{IMDS_BASE}/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2
        )
        token_resp.raise_for_status()
        return token_resp.text

    def get_metadata(self, path, token):
        resp = requests.get(
            f"{IMDS_BASE}{path}",
            headers={"X-aws-ec2-metadata-token": token},
            timeout=2
        )
        resp.raise_for_status()
        return resp.text

    def check(self, instance):
        token = self.get_imds_token()

        instance_id = self.get_metadata(
            "/latest/meta-data/instance-id", token
        )

        region = self.get_metadata(
            "/latest/meta-data/placement/region", token
        )

        ec2 = boto3.client("ec2", region_name=region)

        instance = ec2.describe_instances(
            InstanceIds=[instance_id]
        )["Reservations"][0]["Instances"][0]

        ami_id = instance["ImageId"]

        image = ec2.describe_images(
            ImageIds=[ami_id]
        )["Images"][0]

        creation_date = datetime.fromisoformat(
            image["CreationDate"].replace("Z", "+00:00")
        )

        age_days = (datetime.now(timezone.utc) - creation_date).days

        self.gauge(
            "eks.node.ami.age_days",
            age_days,
            tags=[
                f"instance_id:{instance_id}",
                f"ami:{ami_id}",
                f"region:{region}",
                "source:eks"
            ],
        )