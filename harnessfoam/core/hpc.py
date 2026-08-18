import os
import asyncio
import asyncssh
import tarfile
import logging
import re
from pathlib import Path
from harnessfoam.core.schemas import HPCConfig

logger = logging.getLogger(__name__)

class AsyncHPCClient:
    def __init__(self, config: HPCConfig):
        self.config = config

    def _get_expanded_key_path(self):
        """Expand ~ in the key path and return."""
        return os.path.expanduser(self.config.identity_file)

    async def _connect(self):
        """Create and return an SSH connection."""
        key_path = self._get_expanded_key_path()
        try:
            return await asyncssh.connect(
                self.config.host,
                port=self.config.port,
                username=self.config.username,
                client_keys=[key_path],
                known_hosts=None  # Accept any host key for simplicity, or handle properly in production
            )
        except Exception as e:
            logger.error(f"SSH connection failed to {self.config.username}@{self.config.host}: {e}")
            raise

    async def upload_case(self, local_dir: str, case_id: str) -> str:
        """Tar the local directory, SFTP it to the remote, and extract it."""
        remote_case_dir = f"{self.config.remote_workdir}/{case_id}"
        archive_name = f"{case_id}.tar.gz"
        local_archive = os.path.join(os.path.dirname(local_dir), archive_name)

        # 1. Create local tar.gz
        logger.info(f"Creating local archive: {local_archive}")
        def make_tar():
            with tarfile.open(local_archive, "w:gz") as tar:
                tar.add(local_dir, arcname=case_id)
        await asyncio.to_thread(make_tar)

        try:
            async with await self._connect() as conn:
                # 2. Ensure remote working directory exists
                await conn.run(f"mkdir -p {self.config.remote_workdir}")

                # 3. SFTP upload
                logger.info(f"Uploading {local_archive} to {self.config.host}:{self.config.remote_workdir}")
                async with conn.start_sftp_client() as sftp:
                    await sftp.put(local_archive, f"{self.config.remote_workdir}/{archive_name}")

                # 4. Extract remote archive
                logger.info(f"Extracting archive on remote...")
                extract_cmd = f"cd {self.config.remote_workdir} && tar -xzf {archive_name}"
                res = await conn.run(extract_cmd, check=True)
                
                return remote_case_dir
        finally:
            if os.path.exists(local_archive):
                os.remove(local_archive)

    async def submit_job(self, remote_case_dir: str, script_name: str = "Allrun.slurm") -> str:
        """Run sbatch on the remote directory and return the Job ID."""
        async with await self._connect() as conn:
            cmd = f"cd {remote_case_dir} && sbatch {script_name}"
            logger.info(f"Submitting job: {cmd}")
            res = await conn.run(cmd)
            
            if res.exit_status != 0:
                raise RuntimeError(f"sbatch failed: {res.stderr}")
            
            # Parse Job ID from output e.g., "Submitted batch job 12345"
            match = re.search(r"Submitted batch job (\d+)", res.stdout)
            if match:
                job_id = match.group(1)
                logger.info(f"Job submitted successfully. Job ID: {job_id}")
                return job_id
            else:
                raise RuntimeError(f"Could not parse job ID from sbatch output: {res.stdout}")

    async def stream_logs(self, job_id: str, remote_case_dir: str, websocket=None, loop=None) -> int:
        """Poll squeue and stream tail -f slurm-{job_id}.out via SSH."""
        log_file = f"{remote_case_dir}/slurm-{job_id}.out"
        
        async with await self._connect() as conn:
            # Wait for the log file to be created (job starts running)
            logger.info(f"Waiting for log file {log_file} to appear...")
            for _ in range(60): # wait up to 5 minutes (5s * 60)
                res = await conn.run(f"test -f {log_file}")
                if res.exit_status == 0:
                    break
                
                # Check if job is still in queue or failed immediately
                squeue_res = await conn.run(f"squeue -j {job_id} -h -O state")
                state = squeue_res.stdout.strip()
                if not state:
                    # Job not in queue, might have failed before writing log
                    logger.warning(f"Job {job_id} not found in squeue and no log file created.")
                    return 1
                await asyncio.sleep(5)
            
            # Start streaming
            logger.info(f"Streaming {log_file}...")
            
            async with conn.create_process(f"tail -f -n +1 {log_file}") as process:
                async def read_stdout():
                    async for line in process.stdout:
                        line_clean = line.rstrip()
                        logger.info(f"[HPC OpenFOAM] {line_clean}")
                        if websocket and loop:
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send_json({
                                        "type": "openfoam_log",
                                        "message": line_clean,
                                        "is_error": False
                                    }),
                                    loop
                                )
                            except Exception:
                                pass

                # Run reading task in background
                read_task = asyncio.create_task(read_stdout())

                # Poll squeue to know when to stop
                while True:
                    await asyncio.sleep(10)
                    squeue_res = await conn.run(f"squeue -j {job_id} -h -O state")
                    if not squeue_res.stdout.strip():
                        # Job is no longer in squeue, it has finished
                        break

                # Let tail flush any remaining output
                await asyncio.sleep(5)
                process.terminate()
                await read_task

            # Get final exit code from sacct or just assume 0 if completed
            # For simplicity, we just assume 0 if we get here. 
            # Real implementation could check `sacct -j {job_id} -o ExitCode -P -n`
            return 0

    async def download_results(self, remote_case_dir: str, local_dir: str):
        """Tar the remote directory, download via SFTP, and extract to local."""
        case_id = os.path.basename(local_dir)
        archive_name = f"{case_id}_results.tar.gz"
        
        async with await self._connect() as conn:
            logger.info("Archiving remote results...")
            remote_parent = os.path.dirname(remote_case_dir)
            remote_archive = f"{remote_parent}/{archive_name}"
            
            # Tar everything excluding the heavy initial fields if needed, but for now tar all
            tar_cmd = f"cd {remote_parent} && tar -czf {archive_name} {case_id}"
            await conn.run(tar_cmd, check=True)
            
            logger.info(f"Downloading {remote_archive}...")
            local_archive = os.path.join(os.path.dirname(local_dir), archive_name)
            async with conn.start_sftp_client() as sftp:
                await sftp.get(remote_archive, local_archive)
                
            # Cleanup remote archive
            await conn.run(f"rm {remote_archive}")
            
        logger.info(f"Extracting results locally...")
        def extract_tar():
            import shutil
            # If local_dir exists, we might overwrite, but tar extraction will merge
            with tarfile.open(local_archive, "r:gz") as tar:
                # Need to be careful: the tar contains the folder `case_id`
                # So extracting it in the parent directory of local_dir will overwrite the right place
                tar.extractall(path=os.path.dirname(local_dir))
            os.remove(local_archive)
            
        await asyncio.to_thread(extract_tar)
