#!/usr/bin/env python3
"""
Local test script for the noVNC Docker container.
Tests the same flow as NovncAwsProvider without needing EC2.
Run: python scripts/test_novnc_container.py
"""

import docker
import time
import socket
import urllib.request
import urllib.error
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def wait_for_webdriver_ready(url: str, max_wait: int = 60) -> bool:
    """Poll the WebDriver status endpoint until ready."""
    print(f"Waiting for WebDriver readiness at {url}/status...")
    for i in range(max_wait):
        try:
            with urllib.request.urlopen(f"{url}/status", timeout=2) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    print(f"  [{i+1}s] WebDriver ready! Response: {data[:100]}...")
                    return True
        except (OSError, urllib.error.URLError) as e:
            if i % 5 == 0:  # Log every 5 seconds
                print(f"  [{i+1}s] Still waiting... ({type(e).__name__})")
            time.sleep(1)
    return False


def test_selenium_session(webdriver_url: str) -> bool:
    """Try to create a Selenium session via RemoteWebDriver."""
    print(f"\nTesting Selenium session at {webdriver_url}...")
    try:
        opts = Options()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--headless=new")
        
        driver = webdriver.Remote(
            command_executor=webdriver_url,
            options=opts
        )
        
        print(f"  Session created! Session ID: {driver.session_id}")
        driver.get("https://www.google.com")
        print(f"  Navigated to Google. Title: {driver.title}")
        driver.quit()
        print("  Session closed successfully.")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def main():
    print("=" * 60)
    print("noVNC Container Local Test")
    print("=" * 60)
    
    # 1. Connect to Docker
    print("\n1. Connecting to Docker...")
    try:
        client = docker.from_env()
        print(f"   Docker version: {client.version()['Version']}")
    except Exception as e:
        print(f"   FAILED: Cannot connect to Docker: {e}")
        return 1
    
    # 2. Check if image exists
    print("\n2. Checking for image 'social/novnc-browser:latest'...")
    try:
        image = client.images.get("social/novnc-browser:latest")
        print(f"   Found: {image.short_id}")
    except docker.errors.ImageNotFound:
        print("   Image not found. Building...")
        try:
            image, logs = client.images.build(
                path="infra/docker/novnc-browser/",
                tag="social/novnc-browser:latest",
                rm=True
            )
            for log in logs:
                if 'stream' in log:
                    print(f"   {log['stream'].strip()}")
            print(f"   Built: {image.short_id}")
        except Exception as e:
            print(f"   FAILED to build: {e}")
            return 1
    
    # 3. Start container with DYNAMIC ports (like NovncAwsProvider does)
    print("\n3. Starting container with dynamic port mapping...")
    container_name = f"test_novnc_{int(time.time())}"
    internal_port = 9515
    
    try:
        container = client.containers.run(
            "social/novnc-browser:latest",
            detach=True,
            name=container_name,
            ports={
                f"{internal_port}/tcp": None,  # Dynamic host port
                "6080/tcp": None,
            },
            shm_size='2g'
        )
        print(f"   Container started: {container.short_id} ({container_name})")
    except Exception as e:
        print(f"   FAILED: {e}")
        return 1
    
    try:
        # 4. Wait for port to be assigned
        print("\n4. Waiting for port assignment...")
        host_wd_port = None
        for attempt in range(30):
            container.reload()
            p_wd = container.ports.get(f"{internal_port}/tcp")
            if p_wd:
                host_wd_port = int(p_wd[0]['HostPort'])
                print(f"   Port assigned: container:{internal_port} -> host:{host_wd_port}")
                break
            time.sleep(1)
        
        if not host_wd_port:
            print("   FAILED: Port never assigned")
            return 1
        
        # 5. Check socket connectivity
        print(f"\n5. Testing socket connectivity to localhost:{host_wd_port}...")
        socket_open = False
        for attempt in range(30):
            if is_port_open("localhost", host_wd_port):
                print(f"   Socket is open after {attempt+1} seconds")
                socket_open = True
                break
            time.sleep(1)
        
        if not socket_open:
            print("   FAILED: Socket never opened")
            return 1
        
        # 6. Wait for WebDriver HTTP readiness
        print("\n6. Testing WebDriver HTTP readiness...")
        webdriver_url = f"http://localhost:{host_wd_port}/wd/hub"
        if not wait_for_webdriver_ready(webdriver_url):
            print("   FAILED: WebDriver never became ready")
            # Print container logs for debugging
            print("\n   Container logs (last 50 lines):")
            logs = container.logs().decode('utf-8').split('\n')[-50:]
            for log in logs:
                print(f"   | {log}")
            return 1
        
        # 7. Test Selenium session
        print("\n7. Testing Selenium session...")
        if not test_selenium_session(webdriver_url):
            return 1
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return 0
        
    finally:
        # Cleanup
        print(f"\nCleaning up container {container.short_id}...")
        try:
            container.stop(timeout=5)
            container.remove()
            print("   Removed.")
        except Exception as e:
            print(f"   Cleanup error: {e}")


if __name__ == "__main__":
    exit(main())
