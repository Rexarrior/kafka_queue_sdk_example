#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Credentials
AUTH_USER="admin"
AUTH_PASS="admin123"

echo "=========================================="
echo "Testing Authentication on All Services"
echo "=========================================="
echo ""

# Function to test endpoint
test_endpoint() {
    local service_name=$1
    local endpoint=$2
    local should_require_auth=$3
    local method=${4:-GET}  # Default to GET if not specified
    
    echo -n "Testing $service_name: $endpoint ... "
    
    # Test without auth
    response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$endpoint" 2>&1)
    
    if [ "$should_require_auth" = "true" ]; then
        # Should return 401 without auth
        if [ "$response" = "401" ]; then
            echo -e "${GREEN}✓ Protected (401 without auth)${NC}"
            
            # Test with auth
            echo -n "  With auth: "
            auth_response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -u "$AUTH_USER:$AUTH_PASS" "$endpoint" 2>&1)
            if [ "$auth_response" = "200" ] || [ "$auth_response" = "404" ] || [ "$auth_response" = "502" ] || [ "$auth_response" = "400" ]; then
                echo -e "${GREEN}✓ Works with credentials (${auth_response})${NC}"
            else
                echo -e "${RED}✗ Failed (${auth_response})${NC}"
            fi
        else
            echo -e "${RED}✗ NOT PROTECTED! Got ${response} instead of 401${NC}"
        fi
    else
        # Should NOT require auth (like healthcheck)
        if [ "$response" = "200" ] || [ "$response" = "404" ]; then
            echo -e "${GREEN}✓ Public endpoint (${response})${NC}"
        else
            echo -e "${YELLOW}⚠ Got ${response}${NC}"
        fi
    fi
}

echo "=========================================="
echo "1. IN GATEWAY (port 7091)"
echo "=========================================="
test_endpoint "In Gateway" "http://localhost:7091/in/healthcheck" "false" "GET"
test_endpoint "In Gateway" "http://localhost:7091/in/send" "true" "POST"
echo ""

echo "=========================================="
echo "2. OUT GATEWAY (port 7092)"
echo "=========================================="
test_endpoint "Out Gateway" "http://localhost:7092/out/healthcheck" "false"
test_endpoint "Out Gateway" "http://localhost:7092/out/list_sessions" "true"
test_endpoint "Out Gateway" "http://localhost:7092/out/session_info/by_uid?session_uid=test" "true"
echo ""

echo "=========================================="
echo "3. FILE STORAGE (port 7093)"
echo "=========================================="
test_endpoint "File Storage" "http://localhost:7093/files/healthcheck" "false"
test_endpoint "File Storage" "http://localhost:7093/files/list_files/" "true"
test_endpoint "File Storage" "http://localhost:7093/files/by_address/test/file.txt" "true"
echo ""

echo "=========================================="
echo "4. LOGIC SERVICE ADMIN API (port 7096)"
echo "=========================================="
test_endpoint "Logic Admin" "http://localhost:7096/healthcheck" "false"
test_endpoint "Logic Admin" "http://localhost:7096/auth/status" "false"
test_endpoint "Logic Admin" "http://localhost:7096/requests" "true"
test_endpoint "Logic Admin" "http://localhost:7096/responses" "true"
test_endpoint "Logic Admin" "http://localhost:7096/events" "true"
test_endpoint "Logic Admin" "http://localhost:7096/errors" "true"
echo ""

echo "=========================================="
echo "5. MAIN ADMIN PANEL (port 7094)"
echo "=========================================="
test_endpoint "Main Admin" "http://localhost:7094/healthcheck" "false"
test_endpoint "Main Admin" "http://localhost:7094/auth/status" "false"
test_endpoint "Main Admin" "http://localhost:7094/index.html" "false"
test_endpoint "Main Admin" "http://localhost:7094/admin/queue_info" "true"
test_endpoint "Main Admin" "http://localhost:7094/admin/services/logic/requests" "true"
echo ""

echo "=========================================="
echo "Testing WWW-Authenticate Header"
echo "=========================================="
echo "Checking if protected endpoints return WWW-Authenticate header..."

# Test a few endpoints for WWW-Authenticate header
test_www_auth() {
    local endpoint=$1
    echo -n "  $endpoint: "
    header=$(curl -s -I "$endpoint" 2>&1 | grep -i "WWW-Authenticate")
    if [ -n "$header" ]; then
        echo -e "${YELLOW}Has WWW-Authenticate (may trigger browser prompt)${NC}"
        echo "    $header"
    else
        echo -e "${GREEN}No WWW-Authenticate header${NC}"
    fi
}

test_www_auth "http://localhost:7091/in/send"
test_www_auth "http://localhost:7092/out/list_sessions"
test_www_auth "http://localhost:7093/files/list_files/"
test_www_auth "http://localhost:7096/requests"
test_www_auth "http://localhost:7094/admin/queue_info"

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Check completed. All protected endpoints should:"
echo "  1. Return 401 without authentication"
echo "  2. Work with correct credentials"
echo "  3. Public endpoints (healthcheck, auth/status, static) should work without auth"
echo ""
echo "Note: WWW-Authenticate headers on API endpoints may trigger browser prompts."
echo "=========================================="
