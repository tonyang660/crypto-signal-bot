# Custom AMI Setup Guide for Faster Cirun Runs

## Overview
Creating a custom AMI with AWS CLI pre-installed will eliminate the 30-60 second installation time on every workflow run.

## Steps to Create Custom AMI

### 1. Launch a Base EC2 Instance

```bash
# Launch a t3.micro instance with Ubuntu 22.04 in us-east-2
# Use the AWS Console or CLI:
aws ec2 run-instances \
  --image-id ami-0ea3c35c5c3284d82 \
  --instance-type t3.micro \
  --region us-east-2 \
  --key-name YOUR_KEY_NAME \
  --security-group-ids YOUR_SG_ID \
  --subnet-id YOUR_SUBNET_ID \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=cirun-custom-ami-builder}]'
```

Or use the AWS Console:
- Go to EC2 → Launch Instance
- Name: `cirun-custom-ami-builder`
- AMI: Ubuntu 22.04 LTS (ami-0ea3c35c5c3284d82)
- Instance type: t3.micro
- Region: us-east-2 (Ohio)
- Launch instance

### 2. Connect to Instance and Install Software

```bash
# SSH into your instance
ssh -i your-key.pem ubuntu@YOUR_INSTANCE_IP

# Set environment for non-interactive installation
export DEBIAN_FRONTEND=noninteractive

# Update system (non-interactive)
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

# Install AWS CLI
sudo apt-get install -y unzip curl
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version

# Install other common dependencies that might speed up your workflow
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-pip \
  python3-dev \
  build-essential \
  git

# Clean up to reduce AMI size
sudo apt-get clean
sudo apt-get autoremove -y
rm -rf awscliv2.zip aws/

# Clear bash history and shutdown
history -c
sudo shutdown -h now
```

### 3. Create AMI from Instance

Using AWS Console:
1. Go to EC2 → Instances
2. Select your `cirun-custom-ami-builder` instance
3. Actions → Image and templates → Create image
4. Image name: `cirun-ubuntu-22.04-awscli`
5. Image description: `Ubuntu 22.04 LTS with AWS CLI pre-installed for Cirun`
6. Click "Create image"
7. Wait 5-10 minutes for AMI to be created
8. Go to EC2 → AMIs to see your new AMI ID

Or using AWS CLI:

```bash
# Get your instance ID
INSTANCE_ID="i-xxxxxxxxxxxxxxxxx"  # Replace with your instance ID

# Create AMI
aws ec2 create-image \
  --instance-id $INSTANCE_ID \
  --name "cirun-ubuntu-22.04-awscli" \
  --description "Ubuntu 22.04 LTS with AWS CLI pre-installed for Cirun" \
  --region us-east-2 \
  --no-reboot

# Note the AMI ID from the output
```

### 4. Update .cirun.yml

Once you have your new AMI ID (e.g., `ami-0abc123def456789`), update your `.cirun.yml`:

```yaml
# Cirun configuration for crypto signal bot
runners:
  - name: "aws-runner"
    cloud: "aws"
    
    # Cheap and sufficient for Python bot
    instance_type: "t3.micro"  # 2 vCPU, 1GB RAM
    
    # Custom Ubuntu 22.04 LTS AMI with AWS CLI pre-installed
    machine_image: "ami-YOUR_NEW_AMI_ID"  # Replace with your AMI ID
    
    # Labels to use in workflow
    labels:
      - "cirun-aws"
    
    # Use on-demand instances (more reliable than spot)
    preemptible: false
    
    # Keep runner alive for 1 minute between jobs (matches your cron schedule)
    idle_time: 60  # 1 minute - keeps runner warm for frequent runs
    
    # Use same region as your S3 bucket for faster sync
    region: "us-east-2"
```

### 5. Update trading-bot.yml Workflow

Remove the AWS CLI installation step:

```yaml
steps:
  - name: 📥 Checkout code
    uses: actions/checkout@v4
  
  # Remove this entire step - AWS CLI is now pre-installed in AMI
  # - name: 🔧 Install AWS CLI
  #   run: |
  #     sudo apt-get update -qq
  #     ...
  
  - name: ☁️ Configure AWS credentials
    uses: aws-actions/configure-aws-credentials@v4
    ...
```

### 6. Test the Setup

1. Commit and push your updated `.cirun.yml`
2. Trigger your workflow
3. Verify the AWS CLI step is skipped
4. Check that AWS commands work without installation

### 7. Clean Up

Once your AMI is working:

```bash
# Terminate the builder instance (optional)
aws ec2 terminate-instances \
  --instance-ids $INSTANCE_ID \
  --region us-east-2
```

## Expected Time Savings

- **Before**: ~45-60 seconds for AWS CLI installation
- **After**: ~0 seconds (pre-installed)
- **Total workflow speedup**: ~45-60 seconds per run

With 5-minute cron intervals, this saves:
- ~9-12 minutes per hour
- ~216-288 minutes per day
- **~$0.50-1.00 per month in EC2 costs**

## Additional Optimizations (Optional)

### Pre-install Python Dependencies

If you want to pre-install Python packages to speed up pip install:

```bash
# On your AMI builder instance:
pip3 install --user \
  pandas \
  numpy \
  requests \
  python-binance \
  discord-webhook \
  loguru \
  ta-lib \
  ccxt

# Then create AMI
```

This would save another 10-20 seconds per run.

### Use Spot Instances

For even more cost savings (if reliability isn't critical):

```yaml
# In .cirun.yml
preemptible: true  # Use spot instances (70-90% cheaper)
```

## Troubleshooting

### AMI not found
- Ensure AMI is in the same region (us-east-2)
- Check AMI ID is correct
- Verify AMI status is "available"

### AWS CLI still not found
- Verify you installed AWS CLI correctly in the AMI
- Check that `/usr/local/bin/aws` exists
- Try running `which aws` on the instance before creating AMI

### Workflow still slow
- Check GitHub Actions logs to identify other bottlenecks
- Consider caching Python dependencies with `actions/setup-python@v5` cache
- Monitor S3 sync times
