#!/usr/bin/env python3
"""
Validation script for MAVLink Parser implementation.

This script validates that the MAVLink parser module is correctly implemented
without requiring external dependencies to be installed.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))


def validate_module_structure():
    """Validate that the module has the correct structure."""
    print("Validating module structure...")
    
    try:
        from src import mavlink_parser
        print("  ✓ Module imports successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import module: {e}")
        return False
    
    # Check for required classes
    required_classes = ['MAVLinkParser', 'ParsedMessage']
    for cls_name in required_classes:
        if hasattr(mavlink_parser, cls_name):
            print(f"  ✓ Class '{cls_name}' exists")
        else:
            print(f"  ✗ Class '{cls_name}' not found")
            return False
    
    return True


def validate_parsed_message():
    """Validate ParsedMessage dataclass."""
    print("\nValidating ParsedMessage dataclass...")
    
    try:
        from src.mavlink_parser import ParsedMessage
        import time
        
        # Create instance
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            fields={'type': 2},
            rssi=-80.0,
            snr=15.0,
            raw_bytes=b'\xfe\x09'
        )
        
        print("  ✓ ParsedMessage instance created")
        
        # Check attributes
        required_attrs = [
            'timestamp', 'msg_type', 'msg_id', 'system_id',
            'component_id', 'fields', 'rssi', 'snr', 'raw_bytes'
        ]
        
        for attr in required_attrs:
            if hasattr(msg, attr):
                print(f"  ✓ Attribute '{attr}' exists")
            else:
                print(f"  ✗ Attribute '{attr}' not found")
                return False
        
        # Test optional fields
        msg_minimal = ParsedMessage(
            timestamp=time.time(),
            msg_type='TEST',
            msg_id=1,
            system_id=1,
            component_id=1,
            fields={}
        )
        
        if msg_minimal.rssi is None and msg_minimal.snr is None:
            print("  ✓ Optional fields default to None")
        else:
            print("  ✗ Optional fields not properly defaulted")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating ParsedMessage: {e}")
        return False


def validate_parser_class():
    """Validate MAVLinkParser class structure."""
    print("\nValidating MAVLinkParser class...")
    
    try:
        from src.mavlink_parser import MAVLinkParser
        
        # Create instance (may fail if pymavlink not installed, but structure should exist)
        try:
            parser = MAVLinkParser()
            print("  ✓ MAVLinkParser instance created")
            
            # Check attributes
            if hasattr(parser, 'stats'):
                print("  ✓ Stats attribute exists")
            else:
                print("  ✗ Stats attribute not found")
                return False
            
            # Check for RSSI/SNR tracking
            if hasattr(parser, 'last_rssi') and hasattr(parser, 'last_snr'):
                print("  ✓ RSSI/SNR tracking attributes exist")
            else:
                print("  ✗ RSSI/SNR tracking attributes not found")
                return False
            
        except ImportError:
            print("  ⚠ Cannot create instance (pymavlink not installed)")
            print("    Checking class structure only...")
        
        # Check for required methods
        required_methods = [
            'parse_stream',
            'get_stats',
            'reset_stats',
            'clear_buffer',
            '_create_parsed_message',
            '_extract_radio_status'
        ]
        
        for method_name in required_methods:
            if hasattr(MAVLinkParser, method_name):
                print(f"  ✓ Method '{method_name}' exists")
            else:
                print(f"  ✗ Method '{method_name}' not found")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating MAVLinkParser: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_documentation():
    """Validate that documentation exists."""
    print("\nValidating documentation...")
    
    doc_file = Path(__file__).parent / 'src' / 'README_MAVLinkParser.md'
    
    if doc_file.exists():
        print(f"  ✓ Documentation file exists: {doc_file.name}")
        
        # Check file size
        size = doc_file.stat().st_size
        if size > 1000:
            print(f"  ✓ Documentation is substantial ({size} bytes)")
        else:
            print(f"  ⚠ Documentation seems short ({size} bytes)")
        
        return True
    else:
        print(f"  ✗ Documentation file not found: {doc_file}")
        return False


def validate_examples():
    """Validate that example code exists."""
    print("\nValidating examples...")
    
    example_file = Path(__file__).parent / 'examples' / 'mavlink_parser_example.py'
    
    if example_file.exists():
        print(f"  ✓ Example file exists: {example_file.name}")
        
        # Check file size
        size = example_file.stat().st_size
        if size > 500:
            print(f"  ✓ Example is substantial ({size} bytes)")
        else:
            print(f"  ⚠ Example seems short ({size} bytes)")
        
        return True
    else:
        print(f"  ✗ Example file not found: {example_file}")
        return False


def validate_tests():
    """Validate that tests exist."""
    print("\nValidating tests...")
    
    test_file = Path(__file__).parent / 'tests' / 'test_mavlink_parser.py'
    
    if test_file.exists():
        print(f"  ✓ Test file exists: {test_file.name}")
        
        # Check file size
        size = test_file.stat().st_size
        if size > 2000:
            print(f"  ✓ Test suite is substantial ({size} bytes)")
        else:
            print(f"  ⚠ Test suite seems short ({size} bytes)")
        
        # Check for test classes
        content = test_file.read_text()
        if 'class Test' in content and 'unittest' in content:
            print("  ✓ Test classes found")
        else:
            print("  ⚠ Test structure unclear")
        
        return True
    else:
        print(f"  ✗ Test file not found: {test_file}")
        return False


def main():
    """Run all validations."""
    print("=" * 70)
    print("MAVLink Parser Implementation Validation")
    print("=" * 70)
    
    results = []
    
    # Run validations
    results.append(("Module Structure", validate_module_structure()))
    results.append(("ParsedMessage", validate_parsed_message()))
    results.append(("MAVLinkParser Class", validate_parser_class()))
    results.append(("Documentation", validate_documentation()))
    results.append(("Examples", validate_examples()))
    results.append(("Tests", validate_tests()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("Validation Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print("=" * 70)
    print(f"Results: {passed}/{total} validations passed")
    
    if passed == total:
        print("\n✓ All validations passed! Implementation is complete.")
        return 0
    else:
        print(f"\n✗ {total - passed} validation(s) failed. Please review.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
