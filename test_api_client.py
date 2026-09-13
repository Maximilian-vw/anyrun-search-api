#!/usr/bin/env python3
"""
Quick test script for the ANY.RUN Search API
Run this while the API server is running: python3 api.py
"""

import requests
import sys

BASE_URL = "http://localhost:8000"
API_KEY = "changeme-secure-key-for-local-dev"

def test_health():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"Health: {r.status_code} - {r.json()}")
    return r.status_code == 200

def test_search():
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = {"hash": "A35AC53B052B669ADD060BE266BBFB98DD72F53212A2B4E817D692EA2AB7B934"}
    
    print("Testing search (this takes ~60s)...")
    r = requests.post(f"{BASE_URL}/search", json=data, headers=headers, timeout=120)
    print(f"Search: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        print(f"Found: {len(result)} result(s)")
        for item in result:
            print(f"  - {item.get('verdict')}: {item.get('object')}")
        return True
    else:
        print(f"Error: {r.text}")
        return False

def test_auth():
    # Test without API key
    r = requests.post(f"{BASE_URL}/search", json={"hash": "test"}, timeout=10)
    print(f"No auth: {r.status_code} (expected 401)")
    
    # Test with wrong API key
    r = requests.post(f"{BASE_URL}/search", json={"hash": "test"}, 
                      headers={"X-API-Key": "wrong"}, timeout=10)
    print(f"Wrong key: {r.status_code} (expected 401)")

if __name__ == "__main__":
    print("=== ANY.RUN Search API Test ===\n")
    
    if not test_health():
        print("Health check failed!")
        sys.exit(1)
    
    test_auth()
    print()
    test_search()
    print("\n=== All tests passed ===")