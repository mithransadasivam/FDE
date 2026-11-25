# A private network with no way out to the internet: no internet gateway, no NAT gateway.
# The function reaches Bedrock and Secrets Manager only through private endpoints inside the VPC.
# One subnet keeps the pilot cheap (endpoints are charged per hour per Availability Zone);
# a production deployment uses at least two.

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "pilot" {
  cidr_block           = "10.50.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true # needed for the endpoints' private DNS names
  tags = {
    Name = "uc1-pilot"
  }
}

resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.pilot.id
  cidr_block              = "10.50.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false
  tags = {
    Name = "uc1-pilot-private"
  }
}

resource "aws_security_group" "lambda" {
  name        = "uc1-pilot-lambda"
  description = "The pilot function: outbound HTTPS to the VPC endpoints only"
  vpc_id      = aws_vpc.pilot.id

  egress {
    description = "HTTPS to the endpoints inside the VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.pilot.cidr_block]
  }
}

resource "aws_security_group" "endpoints" {
  name        = "uc1-pilot-endpoints"
  description = "The VPC endpoints: HTTPS from the pilot function only"
  vpc_id      = aws_vpc.pilot.id

  ingress {
    description     = "HTTPS from the pilot function"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }
}
