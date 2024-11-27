from fastapi import APIRouter, UploadFile, HTTPException, Request, Query, File, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import List
import logging
import uuid
import base64
import psycopg2

from .core import Processor
from .core import Authenticator
from ..db.database import Database
from ..redis_manager import RedisManager, RedisConnectionError

router = APIRouter()
processor = Processor()
authenticator = Authenticator()
redis_manager = RedisManager()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# request functions
@router.post("/db/get_user_info")
async def get_user_info(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        with Database() as db:
            user_info = db.get_user_info_w_id(user_id)

        return JSONResponse(
            content={
                "user_id": user_id,
                "user_name": user_info["user_name"],
                "user_surname": user_info["user_surname"],
                "user_type": user_info["user_type"],
            },
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/insert_feedback")
async def insert_feedback(
    userID: str = Query(...),
    feedback_type: str = Form(...),
    feedback_description: str = Form(...),
    feedback_screenshot: UploadFile = File(None),
):
    try:
        feedback_id = str(uuid.uuid4())
        screenshot_data = None

        if feedback_screenshot:
            contents = await feedback_screenshot.read()
            if len(contents) > 2 * 1024 * 1024:  # 2MB limit
                raise HTTPException(
                    status_code=400, detail="Screenshot size should be less than 2MB"
                )
            screenshot_data = base64.b64encode(contents).decode("utf-8")

        with Database() as db:
            db.insert_user_feedback(
                feedback_id=feedback_id,
                user_id=userID,
                feedback_type=feedback_type,
                description=feedback_description[:5000],
                screenshot=screenshot_data,
            )
            db.conn.commit()

        return JSONResponse(
            content={"message": "Thanks for the feedback!"}, status_code=200
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/select_domain")
async def select_domain(
    request: Request,
    userID: str = Query(...),
):
    try:
        data = await request.json()
        selected_domain_number = data.get("currentDomain")
        file_names, domain_name = update_selected_domain(
            user_id=userID, selected_domain=selected_domain_number
        )

        redis_manager.refresh_user_ttl(userID)

        return JSONResponse(
            content={"file_names": file_names, "domain_name": domain_name},
            status_code=200,
        )
    except RedisConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in select_domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/generate_answer")
async def generate_answer(
    request: Request,
    userID: str = Query(...),
):
    try:
        data = await request.json()
        user_message = data.get("user_message")

        # Check if domain is selected
        selected_domain = redis_manager.get_data(f"user:{userID}:selected_domain")
        if not selected_domain:
            return JSONResponse(
                content={"message": "Please select a domain first"},
                status_code=400,
            )

        # Get required data from Redis
        index = redis_manager.get_data(f"user:{userID}:index")
        domain_content = redis_manager.get_data(f"user:{userID}:domain_content")
        boost_info = redis_manager.get_data(f"user:{userID}:boost_info")
        index_header = redis_manager.get_data(f"user:{userID}:index_header")

        if not index or not domain_content:
            return JSONResponse(
                content={"message": "Selected domain is empty!"},
                status_code=400,
            )

        # Process search
        answer, resources, resource_sentences = processor.search_index(
            user_query=user_message,
            domain_content=domain_content,
            boost_info=boost_info,
            index=index,
            index_header=index_header,
        )

        if not answer or not resources or not resource_sentences:
            return JSONResponse(
                content={
                    "message": f"Can you explain the question better? I did not understand '{user_message}'"
                },
                status_code=200,
            )

        redis_manager.refresh_user_ttl(userID)

        return JSONResponse(
            content={
                "answer": answer,
                "resources": resources,
                "resource_sentences": resource_sentences,
            },
            status_code=200,
        )

    except RedisConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in generate_answer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/io/upload_files")
async def upload_files(
    userID: str = Query(...),
    files: List[UploadFile] = File(...),
    lastModified: List[str] = Form(...),
):
    try:
        if not files:
            return JSONResponse(
                content={"message": "No files provided"}, status_code=400
            )

        selected_domain_number = redis_manager.get_data(
            f"user:{userID}:selected_domain"
        )

        # Get domain info
        with Database() as db:
            domain_info = db.get_domain_info(
                user_id=userID, selected_domain_number=selected_domain_number
            )
            if not domain_info:
                return JSONResponse(
                    content={"message": "Invalid domain selected"}, status_code=400
                )

            # Prepare direct insertion tuples
            file_info_batch = []
            file_content_batch = []

            # Process all files
            for file, last_modified in zip(files, lastModified):
                # Validate file
                if not file.filename:
                    continue

                try:
                    file_bytes = await file.read()
                    if not file_bytes:
                        continue

                    file_data = processor.rf.read_file(
                        file_bytes=file_bytes, file_name=file.filename
                    )

                    if not file_data["sentences"]:
                        continue

                    # Prepare batches
                    file_embeddings = processor.ef.create_embeddings_from_sentences(
                        sentences=file_data["sentences"]
                    )
                    file_id = str(uuid.uuid4())
                    file_info_batch.append(
                        (
                            userID,
                            file_id,
                            domain_info["domain_id"],
                            file.filename[:100],  # Truncate here if needed
                            datetime.fromtimestamp(int(last_modified) / 1000).strftime(
                                "%Y-%m-%d"
                            )[:20],
                        )
                    )
                    for i in range(len(file_data["sentences"])):
                        file_content_batch.append(
                            (
                                file_id,
                                file_data["sentences"][i],
                                file_data["page_number"][i],
                                file_data["is_header"][i],
                                file_data["is_table"][i],
                                psycopg2.Binary(file_embeddings[i].tobytes()),
                            )
                        )

                except Exception as e:
                    logging.error(f"Error processing file {file.filename}: {str(e)}")
                    continue

            if not file_info_batch or not file_content_batch:
                return JSONResponse(
                    content={"message": "No valid files to process"}, status_code=400
                )

            # Bulk insertions
            try:
                success = db.insert_file_batches(file_info_batch, file_content_batch)
                if not success:
                    return JSONResponse(
                        content={"message": "Failed to process files"}, status_code=500
                    )
                db.conn.commit()

            except Exception as e:
                logging.error(f"Database error: {str(e)}")
                raise HTTPException(status_code=500, detail="Database error occurred")

        # Update domain info
        file_names, domain_name = update_selected_domain(
            user_id=userID, selected_domain=selected_domain_number
        )

        return JSONResponse(
            content={
                "message": f"Files uploaded successfully to domain {selected_domain_number}",
                "file_names": file_names,
                "domain_name": domain_name,
            },
            status_code=200,
        )

    except KeyError:
        return JSONResponse(
            content={"message": "Please select the domain number first"},
            status_code=200,
        )
    except Exception as e:
        logging.error(f"Error during file upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")

    except KeyError:
        return JSONResponse(
            content={"message": "Please select the domain number first"},
            status_code=200,
        )
    except Exception as e:
        if "db" in locals():
            db.conn.rollback()
        logging.error(f"Error during file upload: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed uploading, error: {str(e)}"
        )


@router.post("/io/remove_file_upload")
async def remove_file_upload(
    request: Request,
    userID: str = Query(...),
):
    try:
        selected_domain_number = redis_manager.get_data(
            f"user:{userID}:selected_domain"
        )
        data = await request.json()
        files = data.get("files_to_remove", [])
        message, file_names, domain_name, status_code = (
            "Unsuccessful deletion!",
            [],
            "",
            500,
        )
        with Database() as db:
            deleted_content, file_ids = db.clear_file_content(
                user_id=userID, files_to_remove=files
            )
            deleted_files = db.clear_file_info(user_id=userID, file_ids=file_ids)
            domain_info = db.get_domain_info(
                user_id=userID, selected_domain_number=selected_domain_number
            )
            file_info = db.get_file_info_with_domain(
                user_id=userID, domain_id=domain_info["domain_id"]
            )
            db.conn.commit()
            message = f"{deleted_files} files and {deleted_content} sentences deleted"
            domain_name = domain_info["domain_name"]
            status_code = 200
        if file_info:
            file_names = [info["file_name"] for info in file_info]

        return JSONResponse(
            content={
                "message": message,
                "domain_name": domain_name,
                "file_names": file_names,
            },
            status_code=status_code,
        )
    except KeyError:
        return JSONResponse(
            content={"message": "Please select the domain number first"},
            status_code=200,
        )
    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during file deletion: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


@router.post("/auth/login")
async def login(
    request: Request,
):
    try:
        data = await request.json()
        user_email = data.get("user_email")
        trial_password = data.get("trial_password")
        message = None
        status_code = 500
        session_id = None
        with Database() as db:
            user_info = db.get_user_info_w_email(user_email=user_email)
            if not user_info or not authenticator.verify_password(
                plain_password=trial_password,
                hashed_password=user_info["user_password"],
            ):
                message = "Invalid email or password"
                status_code = 401
            elif not user_info["is_active"]:
                message = "User is not activated yet. Please contact with --> rahmansahinler1@gmail.com"
                status_code = 401
            else:
                session_id = str(uuid.uuid4())
                db.insert_session_info(user_info["user_id"], session_id=session_id)
                db.conn.commit()
                message = "Login sucessfull"
                status_code = 200

        response = JSONResponse(
            content={"message": message, "session_id": session_id},
            status_code=status_code,
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return response

    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during login: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


@router.post("/auth/signup")
async def signup(
    request: Request,
):
    try:
        data = await request.json()
        user_name = data.get("user_name")
        user_surname = data.get("user_surname")
        user_email = data.get("user_email")
        user_password = data.get("user_password")
        message = None
        status_code = 500
        with Database() as db:
            user_info = db.get_user_info_w_email(user_email=user_email)
            if user_info:
                message = "User already signed up!"
                status_code = 400
            else:
                user_id = str(uuid.uuid4())
                db.insert_user_info(
                    user_id=user_id,
                    user_name=user_name,
                    user_surname=user_surname,
                    user_password=authenticator.hash_password(user_password),
                    user_email=user_email,
                    user_type="trial",
                    is_active=True,
                )
                for i in range(5):
                    db.insert_domain_info(
                        user_id=user_id,
                        domain_id=str(uuid.uuid4()),
                        domain_name=f"Domain {i+1}",
                        domain_number=i + 1,
                    )
                db.conn.commit()
                message = "Successfully Signed Up!"
                status_code = 201

        return JSONResponse(
            content={
                "message": message,
            },
            status_code=status_code,
        )
    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during login: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


# local functions
def update_selected_domain(user_id: str, selected_domain: int):
    try:
        redis_manager.set_data(f"user:{user_id}:selected_domain", selected_domain)

        with Database() as db:
            domain_info = db.get_domain_info(user_id, selected_domain)
            file_info = db.get_file_info_with_domain(user_id, domain_info["domain_id"])

            if not file_info:
                # Clear any existing domain data
                redis_manager.delete_data(f"user:{user_id}:domain_content")
                redis_manager.delete_data(f"user:{user_id}:index")
                redis_manager.delete_data(f"user:{user_id}:index_header")
                redis_manager.delete_data(f"user:{user_id}:boost_info")
                return None, domain_info["domain_name"]

            content, embeddings = db.get_file_content(
                file_ids=[info["file_id"] for info in file_info]
            )

            # Store domain content in Redis
            redis_manager.set_data(f"user:{user_id}:domain_content", content)

            # Process and store boost info
            boost_info = processor.extract_boost_info(
                domain_content=content, embeddings=embeddings
            )
            redis_manager.set_data(f"user:{user_id}:boost_info", boost_info)

            # Create and store main index
            index = processor.create_index(embeddings=embeddings)
            redis_manager.set_data(f"user:{user_id}:index", index)

            # Create and store header index if possible
            try:
                index_header = processor.create_index(
                    embeddings=boost_info["header_embeddings"]
                )
                redis_manager.set_data(f"user:{user_id}:index_header", index_header)
            except IndexError:
                redis_manager.delete_data(f"user:{user_id}:index_header")

            file_names = [info["file_name"] for info in file_info]
            domain_name = domain_info["domain_name"]

            return file_names, domain_name

    except Exception as e:
        logger.error(f"Error in update_selected_domain: {str(e)}")
        raise RedisConnectionError(f"Failed to update domain: {str(e)}")
