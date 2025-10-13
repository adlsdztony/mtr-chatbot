"""
Test script to verify that RAG context is being saved to chat history.

This script simulates the flow of:
1. User asks a question
2. RAG retrieves context
3. AI generates response
4. RAG context is saved to history
5. User asks follow-up question
6. Verify that previous RAG context is in history
"""

import sys
import pathlib

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import (
    get_session_history, 
    add_referenced_context_to_history,
    get_prompted_model
)
from backend.backend import form_context_info
from loguru import logger

def test_rag_context_in_history():
    """Test that RAG context is properly saved to history"""
    
    # Create a test session ID
    test_session_id = "test_session_001"
    
    # Simulate first query
    question1 = "What is the main topic of this document?"
    logger.info(f"\n{'='*60}")
    logger.info(f"First Question: {question1}")
    logger.info(f"{'='*60}\n")
    
    # Get RAG context (simulating what frontend does)
    try:
        texts, images, text_chunks, image_chunks = form_context_info(question1)
        
        logger.info(f"Retrieved {len(text_chunks)} text chunks and {len(image_chunks)} image chunks")
        
        # Simulate AI response (we'll skip the actual model call for this test)
        # In real flow, model generates response here
        
        # Add RAG context to history (this is the new functionality)
        add_referenced_context_to_history(test_session_id, text_chunks, image_chunks)
        
        logger.info("✅ Added RAG context to history")
        
        # Check history
        history = get_session_history(test_session_id)
        logger.info(f"\n📚 Current history length: {len(history.messages)} messages")
        
        # Verify the context was added
        if len(history.messages) > 0:
            last_message = history.messages[-1]
            logger.info(f"Last message type: {type(last_message).__name__}")
            logger.info(f"Last message content preview: {last_message.content[:200]}...")
            
            # Check if it contains the expected markers
            if "REFERENCED CONTEXT FROM RAG RETRIEVAL" in last_message.content:
                logger.info("✅ RAG context successfully saved to history!")
                
                # Count sources in history
                text_source_count = last_message.content.count("[Source")
                logger.info(f"✅ Found {text_source_count} sources in history")
                
                return True
            else:
                logger.error("❌ RAG context not found in history")
                return False
        else:
            logger.error("❌ No messages in history")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_history_persistence():
    """Test that history persists across multiple queries"""
    
    test_session_id = "test_session_002"
    
    logger.info(f"\n{'='*60}")
    logger.info("Testing History Persistence Across Multiple Queries")
    logger.info(f"{'='*60}\n")
    
    # First query
    question1 = "What are the safety features?"
    logger.info(f"Query 1: {question1}")
    
    try:
        texts, images, text_chunks, image_chunks = form_context_info(question1)
        add_referenced_context_to_history(test_session_id, text_chunks, image_chunks)
        
        history_after_q1 = get_session_history(test_session_id)
        count_after_q1 = len(history_after_q1.messages)
        logger.info(f"After Query 1: {count_after_q1} messages in history")
        
        # Second query (simulating follow-up)
        question2 = "Can you explain more about the second feature?"
        logger.info(f"\nQuery 2: {question2}")
        
        texts2, images2, text_chunks2, image_chunks2 = form_context_info(question2)
        add_referenced_context_to_history(test_session_id, text_chunks2, image_chunks2)
        
        history_after_q2 = get_session_history(test_session_id)
        count_after_q2 = len(history_after_q2.messages)
        logger.info(f"After Query 2: {count_after_q2} messages in history")
        
        if count_after_q2 > count_after_q1:
            logger.info("✅ History is accumulating correctly")
            
            # Show all messages in history
            logger.info("\n📋 Full History Contents:")
            for i, msg in enumerate(history_after_q2.messages):
                logger.info(f"\n--- Message {i+1} ({type(msg).__name__}) ---")
                logger.info(f"{msg.content[:300]}...")
            
            return True
        else:
            logger.error("❌ History did not accumulate")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("Starting RAG History Tests\n")
    
    # Run tests
    test1_pass = test_rag_context_in_history()
    test2_pass = test_history_persistence()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Test 1 (RAG Context in History): {'✅ PASSED' if test1_pass else '❌ FAILED'}")
    logger.info(f"Test 2 (History Persistence): {'✅ PASSED' if test2_pass else '❌ FAILED'}")
    logger.info(f"{'='*60}\n")
    
    if test1_pass and test2_pass:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("⚠️ Some tests failed")
        sys.exit(1)
