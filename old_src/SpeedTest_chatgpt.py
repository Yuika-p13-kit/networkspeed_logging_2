# chatGPT 
import speedtest

def do_speedtest():
    st = speedtest.Speedtest()
    st.get_best_server()
    download_speed = st.download()
    upload_speed = st.upload()

    # print(f"Download speed: {download_speed / 1_000_000:.2f} Mbps")
    # print(f"Upload speed: {upload_speed / 1_000_000:.2f} Mbps")

    return download_speed, upload_speed