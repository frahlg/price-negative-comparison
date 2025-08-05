#!/usr/bin/env python3
"""
Test the AI explainer integration with the Flask app
"""

import requests
import json

def test_ai_explainer():
    """Test the AI explainer functionality"""
    
    # App URL
    base_url = "http://127.0.0.1:5000"
    
    # Test uploading a file
    print("Testing AI explainer integration...")
    
    # Use the test file
    test_file_path = "test_sample.csv"
    
    # Prepare form data
    form_data = {
        'area': 'SE_4',
        'currency': 'SEK'
    }
    
    # Upload file
    try:
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test_sample.csv', f, 'text/csv')}
            
            print(f"Uploading {test_file_path} to {base_url}/upload...")
            response = requests.post(
                f"{base_url}/upload",
                data=form_data,
                files=files,
                allow_redirects=False
            )
            
            print(f"Upload response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 302:
                # Successful upload, should redirect to results
                redirect_url = response.headers.get('Location')
                print(f"Redirected to: {redirect_url}")
                
                # Follow redirect to get results
                if redirect_url:
                    # Get cookies from upload response
                    cookies = response.cookies
                    
                    # Request results page
                    results_response = requests.get(f"{base_url}{redirect_url}", cookies=cookies)
                    print(f"Results page status: {results_response.status_code}")
                    
                    if results_response.status_code == 200:
                        # Check if AI explanation is in the response
                        html_content = results_response.text
                        if "AI Analysis Summary" in html_content:
                            print("✅ AI Analysis Summary section found in results!")
                            
                            # Extract the AI explanation from the HTML (basic parsing)
                            import re
                            explanation_match = re.search(
                                r'<div class="explanation-text"[^>]*>(.*?)</div>',
                                html_content,
                                re.DOTALL
                            )
                            
                            if explanation_match:
                                explanation_html = explanation_match.group(1)
                                # Simple HTML to text conversion
                                explanation_text = re.sub(r'<[^>]+>', '', explanation_html)
                                explanation_text = explanation_text.replace('&nbsp;', ' ').strip()
                                
                                print("\n" + "="*50)
                                print("AI EXPLANATION FOUND:")
                                print("="*50)
                                print(explanation_text[:500] + "..." if len(explanation_text) > 500 else explanation_text)
                                print("="*50)
                                
                            else:
                                print("⚠️  AI explanation content not found in HTML")
                        else:
                            print("❌ AI Analysis Summary section not found in results")
                            
                    else:
                        print(f"❌ Failed to get results page: {results_response.status_code}")
                        
            else:
                print(f"❌ Upload failed with status {response.status_code}")
                print(f"Response content: {response.text}")
                
    except FileNotFoundError:
        print(f"❌ Test file {test_file_path} not found")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    test_ai_explainer()
