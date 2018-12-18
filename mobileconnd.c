/**
 * \file mobileconnd.c
 * \brief Guess internet connection status by pinging google.com
 *        and call mobile connection dialing script if needed.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

volatile sig_atomic_t DONE = 0;
pid_t CHILD_PID = -1;

// TODO: Modularize?
const char* const DIALSCRIPT = "autowvdial";
const char* const MODEM      = "/dev/gsmmodem";
const char* const DIALER     = "LTE";
const char* const PIN        = "00000000";
const char* const TIMEOUT    = "60";

void terminate(int signo)
{
    if(signo == SIGTERM || signo == SIGINT)
    {
        DONE = 1;
        kill(CHILD_PID, SIGTERM);
    }
}

int main(int argc, char* argv[])
{
    setbuf(stdout, NULL);
    printf("starting mobileconnd\n");

    struct sigaction action;
    memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = terminate;
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);

    while(!DONE)
    {
        int status = system("ping -c 1 -I ppp0 google.com > /dev/null");
        if(status != EXIT_SUCCESS)
        {
            printf("ping failed\n");

            // Ping failed but we already have a child.
            // Did the dialer script hang or error?
            // Kill the child and spawn a new one.
            if(CHILD_PID != -1)
            {
                printf("autowvdial already running, killing...\n");
                kill(CHILD_PID, SIGTERM);
                sleep(5); // Grace period.
                kill(CHILD_PID, SIGKILL);
                CHILD_PID = -1;
                printf("autowvdial killed\n");
            }

            if((CHILD_PID = fork()) < 0)
            {
                perror("fork error\n");
                exit(EXIT_FAILURE);
            }
            else if(CHILD_PID == 0)
            {
                printf("starting autowvdial\n");
                execlp(DIALSCRIPT, DIALSCRIPT, MODEM, PIN, "-d",
                    DIALER, "-t", TIMEOUT, (char*)NULL);
                perror("execlp error\n");
                _exit(EXIT_FAILURE);
            }
        }
        else
        {
            printf("ping succesful\n");
        }

        printf("sleeping for 5 minutes...\n");
        sleep(60 * 5);
    }

    printf("done, exiting");
    return 0;
}
