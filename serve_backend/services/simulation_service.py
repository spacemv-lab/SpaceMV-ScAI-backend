from typing import Dict, Any, List
import asyncio
import logging
import os
import time
import json
from datetime import datetime
from pathlib import Path
from fastapi.responses import StreamingResponse
from configs.app_config import app_config
import paramiko

class SimulationService:
    """Service for simulation operations"""
    
    async def execute_ssh_command(self, command: str) -> tuple[int, str, str]:
        """
        Execute command on remote SSH server using paramiko
        
        Args:
            command: Command to execute on remote server
            
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=app_config.SSH_HOST,
                username=app_config.SSH_USER,
                password=app_config.SSH_PASSWORD,
                timeout=30
            )
            
            stdin, stdout, stderr = ssh.exec_command(command)
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')
            returncode = stdout.channel.recv_exit_status()
            
            return returncode, stdout_str, stderr_str
        finally:
            ssh.close()
    
    async def execute_local_command(self, command: str) -> tuple[int, str, str]:
        """
        Execute command on local machine
        
        Args:
            command: Command to execute on local machine
            
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode
        
        return returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
    
    async def simulation_stream(self, data: Dict[str, Any]):
        """
        Execute simulation and stream results
        
        Args:
            data: Simulation request data containing ID, level, algorithm_type, start_time, end_time, interval, point_data, line_data, area_data
            
        Returns:
            Streaming response with simulation results
        """
        from constellation_app import get_app
        app = get_app()
        pool = app.state.clickhouse_pool
        
        # Retrieve Simulation Parameters
        simu_paras = data
        
        # Configuration Path
        abs_path = app_config.OUTPUT_DIR
        
        def replace_before_output(old_path, new_base, keyword="output"):
            """
            Replace the portion of the path preceding keyword with new_base, 
            retaining keyword and everything following it（The backend service and STK are not deployed on the same server.）.
            """
            p = Path(old_path)
            parts = p.parts  
            try:
                idx = parts.index(keyword)
            except ValueError:
                raise ValueError(f"路径中没有 {keyword} 文件夹")

            suffix = parts[idx:]

            new_path = Path(new_base, *suffix)
            return str(new_path)
        
        async def event_generator():
            """Generator function for streaming simulation results"""
            client = await pool.acquire()
            try:
                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   数据库已连接\n\n"
                
                 # Single-Star Simulation
                if simu_paras['level'] == 0:
                    logging.info(f"ID为{simu_paras['ID']}的卫星仿真任务开始执行！")
                    yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   ID为{simu_paras['ID']}的卫星仿真任务开始执行！\n\n"
                    
                    query_sat = """
                            SELECT name, tle1, tle2
                            FROM satellites
                            WHERE ID = %(satellite_id)s \
                            """
                    query_sen = """
                            SELECT sensor_type, sensor_value
                            FROM sensor_paras
                            WHERE ID = %(satellite_id)s \
                            """
                    values = {"satellite_id": str(simu_paras['ID'])}

                    try:
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在从数据库提取卫星的轨道和传感器参数......\n\n"
                        result_sat = await client.execute(query_sat, values)
                        result_sen = await client.execute(query_sen, values)
                        
                        if len(result_sat) == 0 or len(result_sen) == 0:
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   没有从数据库查询到卫星的相关信息，任务终止！\n\n"
                            return
                        else:
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   已成功从数据库提取到卫星的相关参数！\n\n"
                            
                        result_sat = result_sat[0]
                        result_sen = result_sen[0]
                        
                        if result_sen[0] == 2:
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   该卫星的搭载的不是光学传感器，目前仿真算法暂不支持，任务终止！\n\n"
                            return
                        else:
                            # Parameter Configuration
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在进行仿真算法的参数配置......\n\n"
                            ID = simu_paras['ID']
                            name = result_sat[0]
                            start_time = datetime.strptime(simu_paras['start_time'], "%Y%m%d%H%M%S").strftime("%Y %m %d %H %M %S")
                            end_time = datetime.strptime(simu_paras['end_time'], "%Y%m%d%H%M%S").strftime("%Y %m %d %H %M %S")
                            interval = simu_paras['interval']
                            tle = result_sat[1].strip() + r'\n' + result_sat[2].strip()
                            attitude_angle = " ".join([result_sen[1][4], result_sen[1][3], result_sen[1][2]])
                            manoeuvrability = result_sen[1][5]
                            area_data = simu_paras['area_data']
                            line_data = simu_paras['line_data']
                            point_data = simu_paras['point_data']

                            mount_path = "/single_satellite/" + name + "_" + ID + "_" + time.strftime("%Y%m%d-%H%M%S")
                            save_dir = abs_path + mount_path
                            simulation_path = save_dir + "/simulation_report"

                            os.makedirs(simulation_path, exist_ok=True)

                            point_path = simulation_path + "/point.txt"
                            line_path = simulation_path + "/line.txt"
                            area_path = simulation_path + "/area.txt"
                            sensor_data = str(float(result_sen[1][0]) * 2) + ' ' + str(float(result_sen[1][1]) * 2)
                            
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   仿真算法的输入参数已配置完成，准备调用算法包进行仿真计算......\n\n"
                            
                            satellites_json = [{"ID": ID, "name": name, "tle1": result_sat[1], "tle2": result_sat[2], "sensor_type": result_sen[0], "sensor_para": result_sen[1]}]
                            satellites_json = json.dumps(satellites_json)
                            satellites_json = satellites_json.replace('"', '\\"')

                            if app_config.STK_LOCAL:
                                # STK On-Premises Deployment
                                exe_path = app_config.STK_PYTHON_LOCAL_EXE
                                script_full_path = app_config.STK_SCRIPT_LOCAL_PATH
                                args = [
                                    script_full_path,
                                    "--start_time", simu_paras['start_time'],
                                    "--end_time", simu_paras['end_time'],
                                    "--step", interval,
                                    "--satellites", satellites_json,
                                    "--path", simulation_path,
                                    "--point", simu_paras['point_data'],
                                    "--line", simu_paras['line_data'],
                                    "--area", simu_paras['area_data']
                                ]
                                local_cmd = f'"{exe_path}" ' + " ".join(f'"{a}"' for a in args)
                                returncode, stdout, stderr = await self.execute_local_command(local_cmd)
                                print(stderr)
                                result = type('obj', (object,), {'returncode': returncode})
                            else:
                                # STK Non-On-Premises Deployment
                                exe_path = app_config.STK_PYTHON_REMOTE_EXE
                                script_full_path = app_config.STK_SCRIPT_REMOTE_PATH
                                args = [
                                    script_full_path,
                                    "--start_time", simu_paras['start_time'],
                                    "--end_time", simu_paras['end_time'],
                                    "--step", interval,
                                    "--satellites", satellites_json,
                                    "--path", replace_before_output(simulation_path, app_config.REPLACE_BASE),
                                    "--point", simu_paras['point_data'],
                                    "--line", simu_paras['line_data'],
                                    "--area", simu_paras['area_data']
                                ]
                                remote_cmd = f'"{exe_path}" ' + " ".join(f'"{a}"' for a in args)
                                returncode, stdout, stderr = await self.execute_ssh_command(remote_cmd)
                                result = type('obj', (object,), {'returncode': returncode})

                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   仿真算法执行完毕，准备确认结果......\n\n"

                            simulation_dict = {}
                            simulation_dict['point'] = (float(point_data.split(' ')[1]), float(point_data.split(' ')[0]))
                            simulation_dict['line'] = list(map(lambda x : (float(x.split(' ')[1]), float(x.split(' ')[0])), line_data.split('|')))
                            simulation_dict['polygon'] = list(map(lambda x : (float(x.split(' ')[1]), float(x.split(' ')[0])), area_data.split('|')))
                            simulation_dict['start_time'] = simu_paras['start_time']
                            simulation_dict['end_time'] = simu_paras['end_time']
                            simulation_dict['save_dir'] = save_dir
                            simulation_dict['mount_path'] = mount_path
                            simulation_dict['result'] = {ID: {'name': name, 'satellite_dir': simulation_path}}
                            simulation_dict['payload'] = name
                            
                            if result.returncode == 0:
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   仿真算法结果已确认！\n\n"
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在构建分析报告......\n\n"
                                
                                # Call the simulation report generation function
                                from libs.report import create_report
                                await create_report(simu_paras['level'], simulation_dict, interval)
                                
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在设置仿真结果可视化页面......\n\n"
                                abs_save_dir = os.path.abspath(save_dir)
                                url = f'/?data_path={os.path.join(abs_save_dir, name)}&zip_path={os.path.join(abs_save_dir, 'report.zip')}'
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   ID为{ID}的卫星仿真任务执行成功，相关结果均已成功生成！\n\n"
                                logging.info(f'ID为{ID}的卫星仿真任务执行成功！')
                                
                                # Generate Simulation Log File.txt
                                dt_start = datetime.strptime(start_time, '%Y %m %d %H %M %S')
                                dt_end = datetime.strptime(end_time, '%Y %m %d %H %M %S')
                                algorithm = 'STK'
                                with open(simulation_path + "/simulation_paras.txt", "a", encoding="utf-8") as f:
                                    f.write(f"卫星名称：{name}\n")
                                    f.write(f"卫星编号：{ID}\n")
                                    f.write(f"tle两行根数：{tle.split(r'\n')}\n")
                                    f.write(f"仿真开始时间：{dt_start.year}年{dt_start.month}月{dt_start.day}日{dt_start.hour}时{dt_start.minute}分{dt_start.second}秒\n")
                                    f.write(f"仿真结束时间：{dt_end.year}年{dt_end.month}月{dt_end.day}日{dt_end.hour}时{dt_end.minute}分{dt_end.second}秒\n")
                                    f.write(f"传感器姿态角：{attitude_angle}\n")
                                    f.write(f"传感器机动能力：{manoeuvrability}\n")
                                    f.write(f"传感器水平视场角：{sensor_data.split(' ')[0]}\n")
                                    f.write(f"传感器垂直视场角：{sensor_data.split(' ')[1]}\n")
                                    f.write(f"观测点目标：{point_data}\n")
                                    f.write(f"观测线目标：{line_data}\n")
                                    f.write(f"观测面目标：{area_data}\n")
                                    f.write(f"仿真算法：{algorithm}\n")
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   仿真任务的参数信息已保存！\n\n"
                                logging.info(f'ID为{ID}的卫星仿真任务的相关执行参数已保存！')
                                yield f"data: __RESULT__:{ {'url': url, 'message':'success'} }\n\n"
                            else:
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   仿真算法结果确认失败，任务终止！\n\n"
                                return

                    except Exception as e:
                        logging.error(f"ID为{simu_paras['ID']}的卫星仿真任务执行出错: {e}")
                        yield f"data: 仿真任务执行出错: {str(e)}\n\n"
                
                # Constellation Simulation
                else:
                    logging.info(f"ID为{simu_paras['ID']}的星座仿真任务开始执行！")
                    yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   ID为{simu_paras['ID']}的星座仿真任务开始执行！\n\n"
                    
                    query_sat = """
                                SELECT ID, name, tle1, tle2
                                FROM satellites
                                WHERE constellation = %(constellation_id)s \
                                """
                    query_con = """
                                SELECT constellation_name
                                FROM constellations
                                WHERE constellation = %(constellation_id)s \
                                """
                    values = {"constellation_id": str(simu_paras['ID'])}

                    try:
                        result_con = await client.execute(query_con, values)
                        constellation_name = result_con[0][0]

                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在从数据库提取星座内所有卫星的轨道和传感器参数......\n\n"
                        result_sat = await client.execute(query_sat, values)
                        ids = [row[0] for row in result_sat]
                        query_sen = """
                                    SELECT ID, sensor_type, sensor_value
                                    FROM sensor_paras
                                    WHERE ID IN %(ids)s\
                                    """
                        values = {"ids": ids}
                        result_sen = await client.execute(query_sen, values)
                        
                        if len(result_sat) == 0 or len(result_sen) == 0:
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   没有从数据库查询到卫星的相关信息，任务终止！\n\n"
                        else:
                            yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   已成功从数据库提取到星座的相关参数！\n\n"
                            
                        sensor_dict = {row[0]: {"sensor_type": row[1], "sensor_para": row[2]} for row in result_sen}
                        satellites_dict = []
                        for row in result_sat:
                            ID = row[0]
                            satellites_dict.append({
                                "ID": ID,
                                "name": row[1],
                                "tle1": row[2],
                                "tle2": row[3],
                                **sensor_dict.get(ID, {})
                            })
                        
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在进行仿真算法的参数配置！\n\n"
                        
                        # Parameter Configuration
                        start_time = datetime.strptime(simu_paras['start_time'], "%Y%m%d%H%M%S").strftime("%Y %m %d %H %M %S")
                        end_time = datetime.strptime(simu_paras['end_time'], "%Y%m%d%H%M%S").strftime("%Y %m %d %H %M %S")
                        interval = simu_paras['interval']
                        area_data = simu_paras['area_data']
                        line_data = simu_paras['line_data']
                        point_data = simu_paras['point_data']
                        dir_name = simu_paras['ID'] + '_' + time.strftime("%Y%m%d-%H%M%S")
                        mount_path = "/constellation/" + dir_name
                        save_dir = abs_path + mount_path
                        satellites_path = save_dir + "/satellites_data"
                        simulation_path = save_dir + "/simulation_report"

                        os.makedirs(satellites_path, exist_ok=True)
                        os.makedirs(simulation_path, exist_ok=True)

                        simulation_dict = {}
                        simulation_dict['point'] = (float(point_data.split(' ')[1]), float(point_data.split(' ')[0]))
                        simulation_dict['line'] = list(map(lambda x : (float(x.split(' ')[1]), float(x.split(' ')[0])), line_data.split('|')))
                        simulation_dict['polygon'] = list(map(lambda x : (float(x.split(' ')[1]), float(x.split(' ')[0])), area_data.split('|')))
                        simulation_dict['start_time'] = simu_paras['start_time']
                        simulation_dict['end_time'] = simu_paras['end_time']
                        simulation_dict['save_dir'] = save_dir
                        simulation_dict['mount_path'] = mount_path
                        simulation_dict['result'] = {}

                        no_optical_id = []
                        no_result_id = []
                        
                        for item in satellites_dict:
                            if item["sensor_type"] == 2:
                                no_optical_id.append(item['ID'])
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   {item['ID']}号卫星搭载不是光学传感器，目前仿真算法暂不支持......\n\n"
                            else:
                                ID = item['ID']
                                name = item['name']
                                tle = item['tle1'].strip() + r'\n' + item['tle2'].strip()
                                attitude_angle = " ".join([item['sensor_para'][4], item['sensor_para'][3], item['sensor_para'][2]])
                                manoeuvrability = item['sensor_para'][5]

                                point_path = satellites_path + '/' + name + "_" + ID + "/point.txt"
                                line_path = satellites_path + '/' + name + "_" + ID + "/line.txt"
                                area_path = satellites_path + '/' + name + "_" + ID + "/area.txt"
                                os.makedirs(satellites_path + '/' + name + "_" + ID, exist_ok=True)
                                sensor_data = str(float(item['sensor_para'][0]) * 2) + ' ' + str(float(item['sensor_para'][1]) * 2)
                                
                                yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在对{ID}号卫星进行仿真计算......\n\n"
                                
                                satellites_json = [{"ID": ID, "name": name, "tle1": item['tle1'], "tle2": item['tle2'],
                                                        "sensor_type": item["sensor_type"], "sensor_para": item['sensor_para']}]
                                satellites_json = json.dumps(satellites_json)
                                satellites_json = satellites_json.replace('"', '\\"')
                                
                                if app_config.STK_LOCAL:
                                    # STK On-Premises Deployment
                                    exe_path = app_config.STK_PYTHON_LOCAL_EXE
                                    script_full_path = app_config.STK_SCRIPT_LOCAL_PATH
                                    args = [
                                        script_full_path,
                                        "--start_time", simu_paras['start_time'],
                                        "--end_time", simu_paras['end_time'],
                                        "--step", interval,
                                        "--satellites", satellites_json,
                                        "--path", satellites_path + '/' + name + "_" + ID,
                                        "--point", simu_paras['point_data'],
                                        "--line", simu_paras['line_data'],
                                        "--area", simu_paras['area_data']
                                    ]
                                    local_cmd = f'"{exe_path}" ' + " ".join(f'"{a}"' for a in args)
                                    returncode, stdout, stderr = await self.execute_local_command(local_cmd)
                                    result = type('obj', (object,), {'returncode': returncode})
                                else:
                                    # STK Non-On-Premises Deployment
                                    exe_path = app_config.STK_PYTHON_REMOTE_EXE
                                    script_full_path = app_config.STK_SCRIPT_REMOTE_PATH
                                    args = [
                                        script_full_path,
                                        "--start_time", simu_paras['start_time'],
                                        "--end_time", simu_paras['end_time'],
                                        "--step", interval,
                                        "--satellites", satellites_json,
                                        "--path", replace_before_output(satellites_path + '/' + name + "_" + ID, app_config.REPLACE_BASE),
                                        "--point", simu_paras['point_data'],
                                        "--line", simu_paras['line_data'],
                                        "--area", simu_paras['area_data']
                                    ]
                                    remote_cmd = f'"{exe_path}" ' + " ".join(f'"{a}"' for a in args)
                                    returncode, stdout, stderr = await self.execute_ssh_command(remote_cmd)
                                    result = type('obj', (object,), {'returncode': returncode})

                                simulation_dict['result'][ID] = {'name': name, 'satellite_dir': satellites_path + '/' + name + "_" + ID}
                                simulation_dict['payload'] = constellation_name
                                
                                if result.returncode != 0:
                                    yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   {ID}号卫星仿真计算的结果确认失败......\n\n"
                                    no_result_id.append(ID)
                                    logging.info(f'{simu_paras['ID']}号星座中ID为{ID}的卫星仿真任务执行失败！')
                                else:
                                    yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   {ID}号卫星仿真计算的结果已确认......\n\n"
                                    logging.info(f'{simu_paras['ID']}号星座中ID为{ID}的卫星仿真任务执行成功！')
                                    
                                    dt_start = datetime.strptime(start_time, '%Y %m %d %H %M %S')
                                    dt_end = datetime.strptime(end_time, '%Y %m %d %H %M %S')

                                    with open(satellites_path + '/' + name + "_" + ID + "/simulation_paras.txt", "a", encoding="utf-8") as f:
                                        f.write(f"卫星名称：{name}\n")
                                        f.write(f"卫星编号：{ID}\n")
                                        f.write(f"tle两行根数：{tle.split(r'\n')}\n")
                                        f.write(f"仿真开始时间：{dt_start.year}年{dt_start.month}月{dt_start.day}日{dt_start.hour}时{dt_start.minute}分{dt_start.second}秒\n")
                                        f.write(f"仿真结束时间：{dt_end.year}年{dt_end.month}月{dt_end.day}日{dt_end.hour}时{dt_end.minute}分{dt_end.second}秒\n")
                                        f.write(f"传感器姿态角：{attitude_angle}\n")
                                        f.write(f"传感器机动能力：{manoeuvrability}\n")
                                        f.write(f"传感器水平视场角：{sensor_data.split(' ')[0]}\n")
                                        f.write(f"传感器垂直视场角：{sensor_data.split(' ')[1]}\n")
                                        f.write(f"观测点目标：{point_data}\n")
                                        f.write(f"观测线目标：{line_data}\n")
                                        f.write(f"观测面目标：{area_data}\n")

                                    yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   {ID}号卫星仿真计算的参数信息已保存......\n\n"
                                    logging.info(f'{simu_paras['ID']}号星座中ID为{ID}的卫星仿真任务的相关执行参数已保存！')
                        
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   星座所有卫星的仿真计算均已完成，正在分析所有仿真结果......\n\n"
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在构建分析报告......\n\n"
                        
                        from libs.report import create_report
                        await create_report(simu_paras['level'], simulation_dict, interval)
                        
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   正在生成仿真结果可视化页面......\n\n"
                        abs_save_dir = os.path.abspath(save_dir)
                        url = f'/?data_path={os.path.join(abs_save_dir, constellation_name)}&zip_path={os.path.join(abs_save_dir, 'report.zip')}'
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   ID为{simu_paras['ID']}的星座仿真任务执行成功，相关结果均已成功生成！\n\n"
                        logging.info(f'{simu_paras['ID']}号星座的仿真任务执行完成！')
                        
                        # Generate Simulation Log File.txt
                        dt_start = datetime.strptime(start_time, '%Y %m %d %H %M %S')
                        dt_end = datetime.strptime(end_time, '%Y %m %d %H %M %S')
                        algorithm = '行业算法' if simu_paras['algorithm_type'] == 1 else 'STK'
                        with open(simulation_path + "/simulation_paras.txt", "a", encoding="utf-8") as f:
                            f.write(f"星座编号：{simu_paras['ID']}\n")
                            f.write(f"仿真开始时间：{dt_start.year}年{dt_start.month}月{dt_start.day}日{dt_start.hour}时{dt_start.minute}分{dt_start.second}秒\n")
                            f.write(f"仿真结束时间：{dt_end.year}年{dt_end.month}月{dt_end.day}日{dt_end.hour}时{dt_end.minute}分{dt_end.second}秒\n")
                            f.write(f"观测点目标：{point_data}\n")
                            f.write(f"观测线目标：{line_data}\n")
                            f.write(f"观测面目标：{area_data}\n")
                            f.write(f"仿真算法：{algorithm}\n")
                        yield f"data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   星座仿真计算的参数信息已保存......\n\n"
                        logging.info(f'{simu_paras['ID']}号星座仿真任务的相关执行参数已保存！')

                        if len(no_optical_id) == 0 and len(no_result_id) == 0:
                            yield f"data: __RESULT__:{ {'url': url, 'message': 'success'} }\n\n"
                            return
                        elif len(no_optical_id) == 0 and len(no_result_id) != 0:
                            yield f"data: __RESULT__:{ {'url': url, 'message': f'success, but the simulation algorithm for the {('、'.join(no_result_id))} satellite in this constellation has encountered an execution error. Please check the input parameter format or review the log.'} }\n\n"
                            return
                        elif len(no_optical_id) != 0 and len(no_result_id) == 0:
                            yield f"data: __RESULT__:{ {'url': url, 'message': f'success, but the {('、'.join(no_optical_id))} satellite sensor in this constellation is of the SAR type and does not currently support simulation calculations.'} }\n\n"
                            return
                        else:
                            yield f"data: __RESULT__:{ {'url': url, 'message': f'success, but the {('、'.join(no_optical_id))} satellite sensor in this constellation is of the SAR type and does not currently support simulation calculations.\
                                                            Additionally, the simulation algorithm for the {('、'.join(no_result_id))} satellite among the remaining satellites has encountered an execution error, please verify the format of the input parameters or review the log.'} }\n\n"
                            return
                    except Exception as e:
                        logging.error(f"{simu_paras['ID']}号星座的仿真任务执行出错: {e}")
                        yield f"data: 仿真任务执行出错: {str(e)}\n\n"
            except Exception as e:
                logging.error(f"仿真执行出错: {str(e)}")
                yield f"data: 仿真任务执行出错: {str(e)}\n\n"
            finally:
                await pool.release(client)

        return StreamingResponse(event_generator(), media_type="text/event-stream")