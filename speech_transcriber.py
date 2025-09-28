"""
Google Speech-to-Text Transcriber using Chirp model
Transcribes audio files using Google Studio AI API
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from google.cloud import speech
from google.oauth2 import service_account
from config import SERVICE_ACCOUNT_FILE, TRANSCRIPTS_DIR, SPEECH_CONFIG


class SpeechTranscriber:
    def __init__(self, use_mock: bool = True):
        # Use service account authentication for Speech-to-Text
        self.service_account_file = SERVICE_ACCOUNT_FILE
        self.transcripts_dir = TRANSCRIPTS_DIR
        self.speech_config = SPEECH_CONFIG.copy()
        self.use_mock = use_mock

        # Initialize client with service account
        if not self.use_mock:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_file
                )
                self.client = speech.SpeechClient(credentials=credentials)
                print("✅ Speech-to-Text client initialized with service account")
            except Exception as e:
                print(f"❌ Speech client initialization failed: {e}")
                print("⚠️ Falling back to mock transcription")
                self.use_mock = True
        else:
            self.client = None
            print("🎭 Using mock transcription (Speech-to-Text API not configured)")

    def transcribe_audio(self, audio_path: str, job_id: str, video_id: str) -> Dict[str, Any]:
        """
        Transcribe audio file using Google Speech-to-Text Chirp model
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return {"error": f"Audio file not found: {audio_path}"}

        print(f"🎙️ Transcribing: {audio_path.name} (Job: {job_id})")

        if self.use_mock:
            return self._mock_transcribe_audio(audio_path, job_id, video_id)

        try:
            # Read audio file
            with open(audio_path, "rb") as audio_file:
                content = audio_file.read()

            # Configure audio settings
            audio = speech.RecognitionAudio(content=content)

            # Configure speech recognition with Chirp model
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.speech_config["sample_rate_hertz"],
                language_code=self.speech_config["language_code"],
                model="chirp",  # Using Chirp model as requested
                use_enhanced=True,
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
            )

            # Perform transcription
            print("🎯 Starting Google Speech-to-Text transcription...")
            response = self.client.recognize(config=config, audio=audio)

            # Process results
            transcription_result = self._process_transcription_response(response)

            # Save transcription to file
            transcript_path = self._save_transcription(transcription_result, job_id, video_id)

            result = {
                "job_id": job_id,
                "video_id": video_id,
                "audio_file": str(audio_path),
                "transcript_path": str(transcript_path),
                "transcription": transcription_result,
                "model": "chirp",
                "language": self.speech_config["language_code"]
            }

            print(f"✅ Transcription complete: {len(transcription_result.get('text', ''))} characters")
            return result

        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            print(f"❌ {error_msg}")

            # Return error result
            return {
                "job_id": job_id,
                "video_id": video_id,
                "audio_file": str(audio_path),
                "error": error_msg,
                "transcription": None
            }

    def _mock_transcribe_audio(self, audio_path: Path, job_id: str, video_id: str) -> Dict[str, Any]:
        """Mock transcription for testing when API is not available"""
        print("🎭 Using mock transcription (simulating Chirp model output)")

        # Get file size to simulate processing time
        file_size = audio_path.stat().st_size / (1024 * 1024)  # MB
        mock_duration = min(file_size * 10, 60)  # Assume ~10 seconds per MB, max 60s

        # Generate mock transcription based on video ID
        mock_transcriptions = {
            "19peKG-nkcs": "Zarkos kidnaps Daphne Blake in this intense scene from Scooby Doo. The villain uses his powers to capture Daphne while the gang tries to stop him.",
            "ThfK2pZA0z4": "Sarah Michelle Gellar as Daphne says I'm not talking to you guys right now. Classic Scooby Doo character moment.",
            "LGp75FI0ZxU": "Daphne gets captured again in this Scooby Doo scene. She always seems to be the one getting kidnapped by the monsters.",
        }

        mock_text = mock_transcriptions.get(video_id, f"This is a mock transcription for Scooby Doo video {video_id}. The Chirp model would transcribe the actual audio content here.")

        # Create mock word timestamps
        words = mock_text.split()
        mock_words = []
        current_time = 0.0
        for word in words:
            word_duration = len(word) * 0.1  # Rough estimate
            mock_words.append({
                "word": word,
                "start_time": current_time,
                "end_time": current_time + word_duration,
            })
            current_time += word_duration + 0.05  # Add small gap

        transcription_result = {
            "text": mock_text,
            "confidence": 0.85,  # Mock confidence score
            "word_timestamps": mock_words,
            "total_words": len(words),
            "duration_seconds": current_time,
            "mock": True,
            "model": "chirp_mock"
        }

        # Save transcription to file
        transcript_path = self._save_transcription(transcription_result, job_id, video_id)

        result = {
            "job_id": job_id,
            "video_id": video_id,
            "audio_file": str(audio_path),
            "transcript_path": str(transcript_path),
            "transcription": transcription_result,
            "model": "chirp_mock",
            "language": self.speech_config["language_code"]
        }

        print(f"✅ Mock transcription complete: {len(mock_text)} characters")
        return result

    def _process_transcription_response(self, response) -> Dict[str, Any]:
        """Process the Speech-to-Text API response"""
        full_text = ""
        confidence_scores = []
        words = []

        for result in response.results:
            alternative = result.alternatives[0]  # Best alternative
            full_text += alternative.transcript + " "

            if result.alternatives[0].confidence:
                confidence_scores.append(result.alternatives[0].confidence)

            # Collect word timestamps if available
            if hasattr(alternative, 'words') and alternative.words:
                for word_info in alternative.words:
                    words.append({
                        "word": word_info.word,
                        "start_time": word_info.start_time.total_seconds() if word_info.start_time else None,
                        "end_time": word_info.end_time.total_seconds() if word_info.end_time else None,
                    })

        # Clean up text
        full_text = full_text.strip()

        return {
            "text": full_text,
            "confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else None,
            "word_timestamps": words,
            "total_words": len(words),
            "duration_seconds": words[-1]["end_time"] if words else None
        }

    def _save_transcription(self, transcription: Dict[str, Any], job_id: str, video_id: str) -> Path:
        """Save transcription results to JSON file"""
        transcript_filename = f"{job_id}_{video_id}_transcript.json"
        transcript_path = self.transcripts_dir / transcript_filename

        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcription, f, indent=2, ensure_ascii=False)

        return transcript_path

    def batch_transcribe(self, audio_files: List[Dict[str, str]], job_id: str) -> List[Dict[str, Any]]:
        """
        Transcribe multiple audio files
        audio_files should contain 'audio_path' and 'video_id' keys
        """
        results = []

        for audio_info in audio_files:
            audio_path = audio_info.get("audio_path")
            video_id = audio_info.get("video_id", "unknown")

            if not audio_path:
                results.append({
                    "video_id": video_id,
                    "error": "No audio path provided"
                })
                continue

            try:
                result = self.transcribe_audio(audio_path, job_id, video_id)
                results.append(result)
            except Exception as e:
                print(f"❌ Batch transcription failed for {video_id}: {e}")
                results.append({
                    "video_id": video_id,
                    "audio_path": audio_path,
                    "error": str(e)
                })

        return results

    def get_transcription_stats(self) -> Dict[str, int]:
        """Get statistics about transcriptions"""
        json_files = list(self.transcripts_dir.glob("*_transcript.json"))
        return {
            "total_transcripts": len(json_files),
            "total_size_mb": round(sum(f.stat().st_size for f in json_files) / (1024 * 1024), 1)
        }


def test_transcriber():
    """Test the speech transcriber with a downloaded audio file"""
    transcriber = SpeechTranscriber()

    # Find a test audio file
    from config import DOWNLOADS_DIR
    test_files = list(DOWNLOADS_DIR.glob("*test_001*.mp3"))

    if not test_files:
        print("❌ No test audio files found. Run media_downloader.py first.")
        return

    test_audio = test_files[0]
    print(f"🧪 Testing transcription with: {test_audio.name}")

    result = transcriber.transcribe_audio(str(test_audio), "test_transcript", "19peKG-nkcs")

    print(f"📊 Test result: {json.dumps(result, indent=2)}")

    # Show transcription stats
    stats = transcriber.get_transcription_stats()
    print(f"📈 Transcription stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    test_transcriber()
